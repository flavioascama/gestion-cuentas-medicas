"""CU-03, flujo alternativo ("si el validador no esta disponible, se aplica
el modo de contingencia"; RF-23, C-18): el analista registra a mano el
resultado de la validacion oficial de un lote cuya carga en TEDEF Web
agoto sus reintentos.

- OBSERVADO: el lote pasa a OBSERVADO_VALIDADOR (sus cuentas siguen
  FACTURADA y entran en un lote nuevo, igual que con el robot).
- VALIDADO: exige el `.S01` que el validador entrego por otro medio (RI-05:
  el sistema nunca lo genera); se guarda en el volumen de artefactos con su
  huella, igual que lo hace CargarLoteEnValidador, y el lote queda VALIDADO
  y listo para remitir (RemitirLote verifica esa huella antes de enviar).

Vive en infraestructura/tedef/ porque escribe el `.S01` en disco."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.compartido.huella import huella_sha256
from app.compartido.nombres_estados import nombre_estado
from app.dominio.contingencia.casos_uso import (
    ConsultarDisponibilidadContingencia,
    validar_sustento,
)
from app.dominio.contingencia.errores import (
    ErrorArchivoS01Invalido,
    ErrorContingenciaNoHabilitada,
)
from app.dominio.contingencia.puertos import RepositorioContingencia
from app.dominio.contingencia.valores import (
    TIPO_EVENTO_VALIDACION_CONTINGENCIA,
    IdentidadLoteS01,
    ResultadoValidacionManual,
)
from app.dominio.integracion.puertos_validacion import ArchivoLote, RepositorioValidacionOficial
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj
from app.infraestructura.tedef.nombrado import PATRON_NOMBRE_S01


@dataclass(frozen=True, slots=True)
class RepositoriosValidacionContingencia:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): los dos
    repositorios que toca el registro manual de la validacion."""

    contingencia: RepositorioContingencia
    validacion: RepositorioValidacionOficial


class RegistrarValidacionContingencia:
    def __init__(
        self,
        disponibilidad: ConsultarDisponibilidadContingencia,
        repositorios: RepositoriosValidacionContingencia,
        observabilidad: Observabilidad,
        reloj: Reloj,
        directorio_artefactos: Path,
    ) -> None:
        self._disponibilidad = disponibilidad
        self._repositorio = repositorios.contingencia
        self._validacion = repositorios.validacion
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._directorio_artefactos = directorio_artefactos

    async def ejecutar(
        self,
        lote_id: int,
        resultado: ResultadoValidacionManual,
        sustento: str,
        archivo_s01: ArchivoLote | None,
        actor: str,
    ) -> str:
        sustento_limpio = validar_sustento(sustento)
        estado_previo = await self._repositorio.obtener_estado_lote(lote_id)
        if not await self._disponibilidad.validacion(lote_id):
            raise ErrorContingenciaNoHabilitada(
                "El modo de contingencia de validación solo se habilita cuando la última "
                "carga de este lote en el validador agotó sus reintentos."
            )
        datos: dict[str, object] = {"modo": "contingencia", "resultado": resultado.value}
        if resultado is ResultadoValidacionManual.VALIDADO:
            estado_nuevo = "VALIDADO"
            identidad = await self._repositorio.identidad_lote_s01(lote_id)
            datos.update(await self._guardar_s01(lote_id, _exigir_s01(archivo_s01, identidad)))
        else:
            estado_nuevo = "OBSERVADO_VALIDADOR"
            await self._repositorio.marcar_lote_observado(lote_id)
        datos["sustento"] = sustento_limpio
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento=TIPO_EVENTO_VALIDACION_CONTINGENCIA,
                actor=actor,
                estado_previo=estado_previo,
                estado_nuevo=estado_nuevo,
                datos=datos,
            )
        )
        return estado_nuevo

    async def _guardar_s01(self, lote_id: int, archivo: ArchivoLote) -> dict[str, object]:
        self._directorio_artefactos.mkdir(parents=True, exist_ok=True)
        ruta = self._directorio_artefactos / archivo.nombre
        ruta.write_bytes(archivo.contenido)
        huella = huella_sha256(archivo.contenido)
        await self._validacion.registrar_archivo_transmision(
            lote_id=lote_id,
            archivo=archivo,
            ruta_s01=str(ruta),
            sha256_s01=huella,
            instante=self._reloj.ahora(),
        )
        return {"nombre_s01": archivo.nombre, "sha256_s01": huella}


def s01_corresponde_al_lote(nombre: str, identidad: IdentidadLoteS01 | None) -> bool:
    """El nombre sigue el patron del Anexo 3 (el mismo con que el sistema
    nombra y reconoce el `.S01`) y lleva el RUC, la IPRESS, la IAFAS, el
    numero y el periodo del lote; la fecha es la del validador."""
    coincidencia = PATRON_NOMBRE_S01.match(nombre)
    if coincidencia is None or identidad is None:
        return False
    return (
        coincidencia["ruc"],
        coincidencia["ipress"],
        coincidencia["iafas"],
        coincidencia["lote"],
        coincidencia["periodo"],
    ) == (
        identidad.ruc,
        identidad.codigo_ipress,
        identidad.codigo_iafas,
        identidad.numero_lote,
        identidad.periodo,
    )


def _exigir_s01(archivo: ArchivoLote | None, identidad: IdentidadLoteS01 | None) -> ArchivoLote:
    if archivo is None:
        raise ErrorArchivoS01Invalido(
            f"Para registrar el lote como {nombre_estado('VALIDADO')} en contingencia hay que "
            "adjuntar el archivo .S01 que entregó el validador."
        )
    if not archivo.contenido:
        raise ErrorArchivoS01Invalido("El archivo .S01 está vacío.")
    nombre = Path(archivo.nombre).name
    if nombre != archivo.nombre or not nombre.upper().endswith(".S01"):
        raise ErrorArchivoS01Invalido(f"El archivo {archivo.nombre} no es un .S01 válido.")
    if not s01_corresponde_al_lote(nombre, identidad):
        raise ErrorArchivoS01Invalido(f"El archivo {nombre} no corresponde a este lote.")
    return archivo
