"""AdaptadorAcreditacionWeb: implementacion Playwright del puerto
AcreditacionWeb (Seccion 8.1, CU-01, puntos 3-4; Seccion 14, supuesto 12:
nombrado por funcion, no por la marca del portal que simula).

Unica implementacion del puerto que vive en el dominio del backend
(app.dominio.acreditacion.puertos.AcreditacionWeb); corre aqui, en el
proceso trabajador (AD-02), porque es la unica pieza del sistema que
importa Playwright.

Desde la Fase 15 (Seccion 8.5: 'deja de ingresar por su cuenta: usa la
sesion asistida') este robot ya no completa usuario/contrasena: carga el
`storage_state` que dejo la sesion asistida (Seccion 8.4) descifrado en
memoria. Si no hay ninguno, o si el que hay ya no autentica de verdad
contra el simulador, lanza `ErrorSesionNoDisponible` -- el dispatcher del
trabajador la distingue de un fallo comun y pasa el trabajo a
REQUIERE_SESION en vez de reintentarlo con retroceso exponencial."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import structlog
from app.dominio.acreditacion.puertos import AcreditacionWeb, ErrorAcreditacion
from app.dominio.acreditacion.valores import (
    ContextoCuentaAcreditacion,
    ResultadoAcreditacion,
    condicion_segun_aseguradora,
    mensaje_asegurado_no_encontrado,
)
from playwright.async_api import Page

from trabajador.configuracion import configuracion
from trabajador.soporte.cifrado import AlmacenSesionesCifrado
from trabajador.soporte.errores import ErrorSesionNoDisponible, ErrorSinResultado
from trabajador.soporte.evidencias import AlmacenEvidenciasCifrado
from trabajador.soporte.navegador import GestorNavegador
from trabajador.soporte.pasos import RegistradorPasos
from trabajador.soporte.selectores import obtener_selector

registro = structlog.get_logger(__name__)

# Solicitud de Atencion Medica (dominio T2 campo 12): el codigo que entrega
# ACREDITA SALUD; la carta de garantia viaja aparte, como segundo documento.
# El codigo de asegurado, el tipo de afiliacion y la IAFAS se leen del
# resultado de la consulta.
_TIPO_DOCUMENTO_AUTORIZACION = "01"

_PLATAFORMA = "acredita_salud"


class ErrorRobotAcreditacion(ErrorAcreditacion):
    pass


@dataclass(frozen=True, slots=True)
class DatosConsulta:
    """Lo que el robot lee del resultado de la consulta del asegurado."""

    codigo_asegurado: str
    tipo_afiliacion: str
    codigo_iafas: str
    nombre_iafas: str
    plan: str | None
    vigente_desde: str | None
    vigente_hasta: str | None
    preexistencias: str | None


class ErrorAseguradoNoEncontrado(ErrorSinResultado):
    """ACREDITA SALUD respondio que no hay un asegurado con ese documento.
    Es una respuesta, no una falla: el mensaje es para el analista, en el
    lenguaje de la clinica (antes decia "El simulador no encontro al
    asegurado 1 73457855", 2026-11-12)."""

    def __init__(self, tipo_documento: str, numero_documento: str) -> None:
        super().__init__(mensaje_asegurado_no_encontrado(tipo_documento, numero_documento))


class AdaptadorAcreditacionWeb(AcreditacionWeb):
    def __init__(
        self,
        gestor_navegador: GestorNavegador,
        almacen_sesiones: AlmacenSesionesCifrado,
        almacen_evidencias: AlmacenEvidenciasCifrado,
        pasos: RegistradorPasos | None = None,
    ) -> None:
        self._gestor_navegador = gestor_navegador
        self._almacen_sesiones = almacen_sesiones
        self._evidencias = almacen_evidencias
        self._pasos = pasos

    async def _paso(self, pagina: Page, descripcion: str) -> None:
        if self._pasos is not None:
            await self._pasos.anotar(pagina, _PLATAFORMA, descripcion)

    async def verificar_cobertura(
        self, contexto: ContextoCuentaAcreditacion, trabajo_id: int
    ) -> ResultadoAcreditacion:
        estado_sesion = self._almacen_sesiones.cargar(_PLATAFORMA)
        if estado_sesion is None:
            raise ErrorSesionNoDisponible(
                "No hay un ingreso activo a ACREDITA SALUD: ingrese con el código de verificación."
            )

        navegador_contexto = await self._gestor_navegador.nuevo_contexto(estado_sesion)
        # C-12: la traza de Playwright es parte de la evidencia (se guarda
        # cifrada junto con la captura al terminar la acreditacion).
        await navegador_contexto.tracing.start(screenshots=True, snapshots=True)
        pagina = await navegador_contexto.new_page()
        try:
            await self._verificar_sesion_vigente(pagina)
            return await self._consultar_y_acreditar(pagina, contexto, trabajo_id)
        except ErrorSesionNoDisponible:
            raise
        except Exception:
            # Seccion 8.1: 'o ante error irrecuperable'. No se sabe en que
            # estado quedo la pagina/contexto tras una excepcion a mitad
            # de flujo, asi que no vale la pena intentar reutilizarlo: el
            # proximo trabajo arranca con un navegador limpio.
            registro.warning("robot_acreditacion_error", trabajo_id=trabajo_id)
            await self._gestor_navegador.reiniciar()
            raise
        finally:
            await navegador_contexto.close()

    async def _verificar_sesion_vigente(self, pagina: Page) -> None:
        """Ya no reautentica por su cuenta (Seccion 8.5): si la sesion
        cargada no basta para entrar, la unica salida es REQUIERE_SESION,
        no un reintento indefinido."""

        await pagina.goto(f"{configuracion.acredita_salud_url_base}/menu")
        if pagina.url.endswith("/ingreso"):
            raise ErrorSesionNoDisponible(
                "El ingreso a ACREDITA SALUD venció: vuelva a ingresar con el código de "
                "verificación."
            )
        await self._paso(pagina, "Menú principal, con la sesión iniciada")

    async def _consultar_y_acreditar(
        self, pagina: Page, contexto: ContextoCuentaAcreditacion, trabajo_id: int
    ) -> ResultadoAcreditacion:
        base = configuracion.acredita_salud_url_base
        ruta_consulta = obtener_selector("consulta_iafas", "ruta")
        await pagina.goto(f"{base}{ruta_consulta}")
        await pagina.select_option(
            obtener_selector("consulta_iafas", "campo_tipo_documento"),
            contexto.tipo_documento_paciente,
        )
        await pagina.fill(
            obtener_selector("consulta_iafas", "campo_numero_documento"),
            contexto.numero_documento_paciente,
        )
        await pagina.click(obtener_selector("consulta_iafas", "boton_buscar"))
        await pagina.wait_for_selector(obtener_selector("consulta_iafas", "resultado"))
        await self._paso(pagina, "Consulta del asegurado")

        if await pagina.locator(obtener_selector("consulta_iafas", "no_encontrado")).count() > 0:
            raise ErrorAseguradoNoEncontrado(
                contexto.tipo_documento_paciente, contexto.numero_documento_paciente
            )
        consulta = await self.leer_consulta(pagina)

        await pagina.click(obtener_selector("consulta_iafas", "enlace_acreditar"))
        await pagina.wait_for_selector(obtener_selector("evaluacion", "condicion_cobertura"))
        await self._paso(pagina, "Evaluación de la cobertura")
        # La IAFAS que responde debe ser la de la cuenta: si no, no se
        # factura a la aseguradora equivocada.
        condicion_cobertura = condicion_segun_aseguradora(
            await self._texto_requerido(pagina, "evaluacion", "condicion_cobertura"),
            contexto.codigo_iafas,
            consulta.codigo_iafas,
            consulta.nombre_iafas,
        )
        copago = await self._leer_copago(pagina)

        await pagina.click(obtener_selector("evaluacion", "boton_generar"))
        await pagina.wait_for_selector(obtener_selector("documento", "codigo_autorizacion"))
        await self._paso(pagina, "Documento de acreditación generado")

        codigo_autorizacion = await self._texto_requerido(
            pagina, "documento", "codigo_autorizacion"
        )
        ruta_evidencia = await self._guardar_evidencia(
            pagina, trabajo_id, contexto, codigo_autorizacion
        )

        return ResultadoAcreditacion(
            condicion_cobertura=condicion_cobertura,
            codigo_autorizacion=codigo_autorizacion,
            tipo_documento_autorizacion=_TIPO_DOCUMENTO_AUTORIZACION,
            codigo_asegurado=consulta.codigo_asegurado,
            tipo_afiliacion=consulta.tipo_afiliacion,
            plan=consulta.plan,
            vigente_desde=_fecha_opcional(consulta.vigente_desde),
            vigente_hasta=_fecha_opcional(consulta.vigente_hasta),
            tipo_copago=copago[0],
            monto_copago_fijo=copago[1],
            porcentaje_coaseguro=copago[2],
            preexistencias=[consulta.preexistencias] if consulta.preexistencias else [],
            ruta_evidencia=ruta_evidencia,
        )

    async def leer_consulta(self, pagina: Page) -> DatosConsulta:
        """Los datos del asegurado tal como los muestra el resultado de la
        consulta (selectores con clave fija, no por posicion)."""
        return DatosConsulta(
            codigo_asegurado=await self._texto_requerido(
                pagina, "consulta_iafas", "codigo_asegurado"
            ),
            tipo_afiliacion=await self._texto_requerido(
                pagina, "consulta_iafas", "tipo_afiliacion"
            ),
            codigo_iafas=await self._texto_requerido(pagina, "consulta_iafas", "codigo_iafas"),
            nombre_iafas=await self._texto_opcional(pagina, "consulta_iafas", "nombre_iafas") or "",
            plan=await self._texto_opcional(pagina, "consulta_iafas", "plan"),
            vigente_desde=await self._texto_opcional(pagina, "consulta_iafas", "vigente_desde"),
            vigente_hasta=await self._texto_opcional(pagina, "consulta_iafas", "vigente_hasta"),
            preexistencias=await self._texto_opcional(pagina, "consulta_iafas", "preexistencias"),
        )

    async def _leer_copago(self, pagina: Page) -> tuple[str | None, Decimal | None, int | None]:
        tipo_copago = await self._texto_opcional(pagina, "evaluacion", "tipo_copago")
        if tipo_copago == "Sin copago":
            tipo_copago = None
        monto_copago_fijo = _decimal_opcional(
            await self._texto_opcional(pagina, "evaluacion", "monto_copago_fijo")
        )
        porcentaje_coaseguro = _entero_opcional(
            await self._texto_opcional(pagina, "evaluacion", "porcentaje_coaseguro")
        )
        return tipo_copago, monto_copago_fijo, porcentaje_coaseguro

    async def _texto_opcional(self, pagina: Page, seccion: str, clave: str) -> str | None:
        locador = pagina.locator(obtener_selector(seccion, clave))
        if await locador.count() == 0:
            return None
        # text_content() lee el DOM tal cual, sin exigir que el elemento
        # este visible -- a diferencia de inner_text(), que devuelve
        # cadena vacia para los campos con clave fija que el simulador
        # oculta a la vista (ya se muestran, con su etiqueta, en otra
        # parte de la misma pagina; ver plantillas/iafas.html, Fase 11).
        texto = await locador.text_content()
        texto = (texto or "").strip()
        return texto or None

    async def _texto_requerido(self, pagina: Page, seccion: str, clave: str) -> str:
        texto = await self._texto_opcional(pagina, seccion, clave)
        if texto is None:
            raise ErrorRobotAcreditacion(f"El selector '{seccion}.{clave}' no devolvio texto.")
        return texto

    async def _guardar_evidencia(
        self,
        pagina: Page,
        trabajo_id: int,
        contexto: ContextoCuentaAcreditacion,
        codigo_autorizacion: str,
    ) -> str:
        # C-12 y RNF-16: nada de la evidencia toca el disco sin cifrar.
        carpeta = f"evidencia_acreditacion/{trabajo_id}"
        ruta_captura = self._evidencias.guardar(
            f"{carpeta}/documento.png", await pagina.screenshot()
        )
        traza = {
            "trabajo_id": trabajo_id,
            "cuenta_medica_id": contexto.cuenta_medica_id,
            "documento_paciente": (
                f"{contexto.tipo_documento_paciente} {contexto.numero_documento_paciente}"
            ),
            "codigo_autorizacion": codigo_autorizacion,
            "url_final": pagina.url,
            "capturado_en": datetime.now(UTC).isoformat(),
        }
        self._evidencias.guardar(
            f"{carpeta}/traza.json", json.dumps(traza, indent=2, ensure_ascii=False).encode()
        )
        with tempfile.TemporaryDirectory() as temporal:
            archivo_traza = Path(temporal) / "traza_playwright.zip"
            await pagina.context.tracing.stop(path=str(archivo_traza))
            self._evidencias.guardar(f"{carpeta}/traza_playwright.zip", archivo_traza.read_bytes())
        return ruta_captura


def _fecha_opcional(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


def _decimal_opcional(texto: str | None) -> Decimal | None:
    if texto is None:
        return None
    limpio = texto.replace("S/", "").strip()
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def _entero_opcional(texto: str | None) -> int | None:
    if texto is None:
        return None
    limpio = texto.replace("%", "").strip()
    return int(limpio) if limpio.isdigit() else None
