"""Configuracion centralizada del backend, leida de variables de entorno.

Ningun valor normativo (longitudes, formatos, dominios TEDEF) vive aqui: eso
se lee de configuracion/esquema_tedef, configuracion/reglas_tedef y
configuracion/mapeo. Este modulo solo resuelve parametros de despliegue.
"""

import re
from datetime import date
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRETOS = {
    "url_base_datos": "URL_BASE_DATOS",
    "clave_firma_sesion": "CLAVE_FIRMA_SESION",
    "clave_hmac_eventos": "CLAVE_HMAC_EVENTOS",
    "ftp_receptor_iafas_clave": "FTP_RECEPTOR_IAFAS_CLAVE",
    "clave_cifrado_datos": "CLAVE_CIFRADO_DATOS",
}


class Configuracion(BaseSettings):
    """Parametros de entorno del backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    entorno: str = Field(default="desarrollo", alias="ENTORNO")
    nivel_log: str = Field(default="INFO", alias="NIVEL_LOG")
    url_base_datos: str = Field(default="", alias="URL_BASE_DATOS")
    # C-10 y RAS-11: las migraciones corren con el dueno del esquema; la
    # aplicacion, con un rol sin superusuario. Vacio: se usa URL_BASE_DATOS.
    url_base_datos_migraciones: str = Field(default="", alias="URL_BASE_DATOS_MIGRACIONES")
    clave_firma_sesion: str = Field(default="", alias="CLAVE_FIRMA_SESION")
    # Control C-01 (Seccion 5.2.7 de la tesis): "sesenta minutos". Bajado
    # desde los 480 minutos originales de la Fase 18 (Fase 22,
    # docs/DECISIONES.md).
    duracion_sesion_minutos: int = Field(default=60, alias="DURACION_SESION_MINUTOS")
    # Control C-01: "tras cinco intentos fallidos la cuenta se bloquea
    # durante quince minutos".
    maximo_intentos_fallidos_sesion: int = Field(default=5, alias="MAXIMO_INTENTOS_FALLIDOS_SESION")
    duracion_bloqueo_sesion_minutos: int = Field(
        default=15, alias="DURACION_BLOQUEO_SESION_MINUTOS"
    )
    # Fase 24 (Seccion 6.2.2, RNF-18, AD-11): clave del encadenamiento con
    # valor resumen (HMAC-SHA256) del almacen de eventos, fuera de la base
    # de datos. Sin valor por defecto (RNF-11, C-06): se exige en .env y no
    # puede cambiarse despues del primer evento sin invalidar la cadena.
    clave_hmac_eventos: str = Field(default="", alias="CLAVE_HMAC_EVENTOS")
    # Fase 27 (Seccion 5.2.4.3, Tabla 61): a diferencia de los tres plazos
    # de la Tabla 61 asociados a la aseguradora (columnas de `iafas`, por
    # convenio), el plazo de reenvio de un lote rechazado es "parametro
    # del sistema, definido por la institucion" -- no varia por IAFAS --
    # por eso vive aqui, igual que `duracion_sesion_minutos` (control
    # C-01, tambien "parametro del sistema").
    dias_plazo_reenvio_lote_rechazado: int = Field(
        default=5, alias="DIAS_PLAZO_REENVIO_LOTE_RECHAZADO"
    )
    # Ventana de aviso previo al vencimiento, uniforme para los hitos 1, 3
    # y 4 de la Tabla 61: la tesis no fija un numero de dias para "la
    # proximidad del vencimiento" (solo los plazos mismos son parametros
    # por convenio); se adopta un unico parametro de sistema para no
    # tener que justificar un numero distinto por hito sin respaldo en
    # la tesis.
    dias_aviso_previo_vencimiento: int = Field(default=2, alias="DIAS_AVISO_PREVIO_VENCIMIENTO")
    # Hito 5 de la Tabla 61 (vigencia de la carta de garantia): mismo
    # razonamiento que la ventana de arriba, ventana propia porque la
    # vigencia de un documento de la aseguradora no es comparable en
    # magnitud a los plazos de respuesta administrativa.
    dias_aviso_vigencia_carta_garantia: int = Field(
        default=5, alias="DIAS_AVISO_VIGENCIA_CARTA_GARANTIA"
    )
    # Temporizador del sistema (CU-11, RNF-18; app/infraestructura/
    # temporizador.py): cada cuanto corre el control de plazos, y cada
    # cuanto el anclaje y la verificacion de la cadena de eventos (la
    # tesis dice "diario": 24 horas).
    temporizador_intervalo_vencimientos_minutos: int = Field(
        default=60, alias="TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS"
    )
    temporizador_intervalo_cadena_horas: int = Field(
        default=24, alias="TEMPORIZADOR_INTERVALO_CADENA_HORAS"
    )
    # Cada cuanto se revisan el portal y el correo de la IAFAS.
    temporizador_intervalo_comunicaciones_minutos: int = Field(
        default=15, alias="TEMPORIZADOR_INTERVALO_COMUNICACIONES_MINUTOS"
    )
    # RI-16 / RT-05: dias no habiles para el plazo de envio a SUSALUD
    # (fechas ISO separadas por comas). Vacio: solo se excluyen sabados y
    # domingos, y la fecha limite calculada nunca es posterior a la real.
    feriados: str = Field(default="", alias="FERIADOS")
    # C-05 y RNF-16: clave Fernet de las columnas sensibles. No se puede
    # cambiar sin volver a cifrar los datos.
    clave_cifrado_datos: str = Field(default="", alias="CLAVE_CIFRADO_DATOS")
    # C-12: plazo de retencion de las evidencias del robot. La tesis no fija
    # uno; se adopta el de la bitacora (dos anios, RNF-10) como supuesto.
    retencion_evidencias_dias: int = Field(default=730, alias="RETENCION_EVIDENCIAS_DIAS")
    # Donde el trabajador deja las evidencias cifradas y su clave Fernet: el
    # servidor las lee para mostrar la Solicitud de Atencion Medica.
    ruta_reportes: str = Field(default="/reportes", alias="RUTA_REPORTES")
    clave_cifrado_evidencias: str = Field(default="", alias="CLAVE_CIFRADO_EVIDENCIAS")

    # --- Simulador receptor IAFAS / FTP (Fase 8, Seccion 9.2) ---
    ftp_receptor_iafas_host: str = Field(default="localhost", alias="FTP_RECEPTOR_IAFAS_HOST")
    ftp_receptor_iafas_puerto: int = Field(default=2121, alias="FTP_RECEPTOR_IAFAS_PUERTO")
    ftp_receptor_iafas_usuario: str = Field(
        default="ipress_local", alias="FTP_RECEPTOR_IAFAS_USUARIO"
    )
    ftp_receptor_iafas_clave: str = Field(default="", alias="FTP_RECEPTOR_IAFAS_CLAVE")

    # Portal web de ese mismo simulador (Fase 12, Seccion 8.3): puerto
    # HTTP interno de contenedor, no el FTP de arriba.
    receptor_iafas_url_base: str = Field(
        default="http://localhost:8101", alias="RECEPTOR_IAFAS_URL_BASE"
    )

    # URLs de los otros dos simuladores (Fases 10 y 14): el backend no las
    # usaba hasta la Fase 20 -- solo el trabajador les habla directo
    # (Playwright). Las necesita aqui unicamente
    # herramientas/generar_evidencia_sesiones_plataformas.py y las demas
    # herramientas de evidencia, para leer "GET /admin/configuracion" y
    # declarar en la cabecera la latencia artificial realmente vigente en
    # cada simulador durante esa ejecucion (Seccion 13).
    acredita_salud_url_base: str = Field(
        default="http://localhost:8100", alias="ACREDITA_SALUD_URL_BASE"
    )
    tedef_web_url_base: str = Field(default="http://localhost:8102", alias="TEDEF_WEB_URL_BASE")

    # Simulador PSE (adenda de ingesta y completitud): emision sincrona del
    # comprobante de pago, sin sesion asistida (a diferencia de los dos de
    # arriba, un PSE real es API-a-API, no un portal navegado por un
    # humano) -- el backend le habla directo desde la ruta HTTP, el
    # trabajador no participa.
    pse_url_base: str = Field(default="http://localhost:8103", alias="PSE_URL_BASE")

    # Sistema hospitalario de la clinica (2026-11-19): de el se importa la
    # atencion cerrada. API a API, como el PSE, con la clave en la cabecera
    # X-Clave-Api. La clave no tiene valor por defecto en el codigo.
    sistema_hospitalario_url_base: str = Field(
        default="http://localhost:8104", alias="SISTEMA_HOSPITALARIO_URL_BASE"
    )
    sistema_hospitalario_clave: str = Field(default="", alias="SISTEMA_HOSPITALARIO_CLAVE")

    # Origenes permitidos por CORS (Fase 19, Seccion 12): la aplicacion
    # web corre en un origen distinto al backend (Vite en el puerto 5173
    # en desarrollo), asi que el navegador exige la cabecera CORS. Lista
    # separada por comas; nunca "*" (la API exige credenciales/Bearer).
    origenes_cors: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="ORIGENES_CORS"
    )

    @model_validator(mode="after")
    def _exigir_secretos(self) -> "Configuracion":
        """RNF-11 y C-06 (verificacion de cumplimiento, 2026-11-12): las
        claves no tienen valor por defecto en el codigo versionado; si
        falta alguna en el entorno (.env), el proceso no arranca."""
        faltantes = [alias for campo, alias in _SECRETOS.items() if not getattr(self, campo)]
        if faltantes:
            raise ValueError("Faltan en el entorno (.env): " + ", ".join(faltantes))
        return self

    @model_validator(mode="after")
    def _exigir_tls(self) -> "Configuracion":
        """C-04 y RNF-15 (2026-11-13): fuera del entorno de desarrollo, cuyos
        simuladores no ofrecen TLS (supuesto 7, Seccion 14), toda plataforma
        externa se alcanza por https y la base por una conexion cifrada."""
        if self.entorno == "desarrollo":
            return self
        sin_tls = [
            alias
            for alias, url in (
                ("ACREDITA_SALUD_URL_BASE", self.acredita_salud_url_base),
                ("TEDEF_WEB_URL_BASE", self.tedef_web_url_base),
                ("PSE_URL_BASE", self.pse_url_base),
                ("SISTEMA_HOSPITALARIO_URL_BASE", self.sistema_hospitalario_url_base),
                ("RECEPTOR_IAFAS_URL_BASE", self.receptor_iafas_url_base),
            )
            if not url.startswith("https://")
        ]
        if not re.search(r"[?&]ssl=(require|verify-ca|verify-full)", self.url_base_datos):
            sin_tls.append("URL_BASE_DATOS (ssl=require)")
        if sin_tls:
            raise ValueError("Canales sin TLS fuera de desarrollo: " + ", ".join(sin_tls))
        return self

    @property
    def conjunto_feriados(self) -> frozenset[date]:
        return frozenset(
            date.fromisoformat(f.strip()) for f in self.feriados.split(",") if f.strip()
        )

    @property
    def lista_origenes_cors(self) -> list[str]:
        return [origen.strip() for origen in self.origenes_cors.split(",") if origen.strip()]


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Punto unico de acceso a la configuracion, cacheado por proceso."""

    return Configuracion()
