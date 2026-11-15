"""Modelos SQLAlchemy del dominio de integracion (Seccion 6.1).

Fase 7: asegurado, iafas, ipress, cuenta_medica, acreditacion,
procedimiento_facturado, documento_facturador, lote_facturacion,
lote_documento, maestro_iafas, maestro_ipress, evento y medicion_paso.
Fase 8: acuse_transmision. Fase 11: trabajo -- la cola transaccional, ya
consumida por el proceso trabajador de sistema/automatizacion/ (Seccion
13); con la tabla creada, RemitirLote (Fase 8) ya encola el paso 6 que
tenia diferido ("inserta un trabajo MONITOREAR_RESPUESTA_IAFAS") -- ver
docs/DECISIONES.md, Fase 11.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.cifrado_columnas import TextoCifrado, indice_ciego

# Seccion 5.2.4 (Fase 25, Tabla 58): los catorce estados del motor de
# orquestacion -- antes de esa fase, solo existian los cuatro del OE1
# (REGISTRADA, FACTURADA, ENVIADA, RECHAZADA), sin motor de transiciones.
# El conjunto y el orden siguen la Tabla 58; `app.dominio.orquestacion.
# motor` es quien decide cuales transiciones entre ellos son admisibles.
ESTADOS_CUENTA_MEDICA = (
    "REGISTRADA",
    "FACTURADA",
    "ENVIADA",
    "EN_AUDITORIA",
    "GLOSADA",
    "GLOSADA_PARCIAL",
    "SUBSANADA",
    "LIQUIDADA",
    "LIQUIDADA_PARCIAL",
    "PAGADA",
    "PAGADA_PARCIAL",
    "RECHAZADA",
    "CERRADA",
    "ANULADA",
)


class IafasModelo(Base):
    __tablename__ = "iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(sa.String(5), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    periodicidad_remision_dias: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ventana_monitoreo_horas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Fase 27 (Seccion 5.2.4.3, Tabla 61): tres de los cinco hitos
    # controlados son "parametro asociado a la aseguradora, con origen en
    # el convenio suscrito con ella" -- mismo patron que las dos columnas
    # de arriba, ya del OE1. Con valor por defecto (igual al de la
    # migracion `a900765e4e0d`) para que las fixtures de IAFAS de fases
    # anteriores, ajenas al control de plazos, no tengan que conocerlas.
    dias_plazo_respuesta_observacion: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=7
    )
    dias_plazo_comunicacion_auditoria: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=30
    )
    dias_plazo_pago_liquidacion: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=30)


class IpressModelo(Base):
    __tablename__ = "ipress"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(sa.String(11), unique=True, nullable=False)
    codigo_ipress: Mapped[str] = mapped_column(sa.String(8), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)


class AseguradoModelo(Base):
    __tablename__ = "asegurado"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    # C-05 y RNF-16 (2026-11-13): identidad del asegurado cifrada en reposo;
    # la busqueda por documento usa el indice ciego.
    numero_documento: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    nombres: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    apellidos: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    documento_indice: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    iafas_id: Mapped[int] = mapped_column(sa.ForeignKey("iafas.id"), nullable=False)
    ficticio: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = ()


@sa.event.listens_for(AseguradoModelo, "before_insert")
@sa.event.listens_for(AseguradoModelo, "before_update")
def _calcular_indice_documento(
    _mapper: object, _conexion: object, asegurado: AseguradoModelo
) -> None:
    """C-05: el indice ciego del documento se mantiene solo, sea quien sea
    quien inserte o actualice al asegurado."""
    asegurado.documento_indice = indice_ciego(asegurado.tipo_documento, asegurado.numero_documento)


class AcreditacionModelo(Base):
    """Seccion 6.1: condicion de cobertura, codigo de autorizacion,
    vigencia, plan, copagos, preexistencias, instante, duracion,
    componente ejecutor, ruta de evidencia."""

    __tablename__ = "acreditacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    condicion_cobertura: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    codigo_autorizacion: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    tipo_documento_autorizacion: Mapped[str] = mapped_column(sa.String(2), nullable=False)
    codigo_asegurado: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    tipo_afiliacion: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    plan: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    vigente_desde: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    # 'fijo' o 'coaseguro'.
    tipo_copago: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    monto_copago_fijo: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    porcentaje_coaseguro: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    preexistencias: Mapped[list[Any]] = mapped_column(sa.JSON, nullable=False, default=list)
    instante: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    duracion_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    componente_ejecutor: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    ruta_evidencia: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    cuenta: Mapped[CuentaMedicaModelo] = relationship(back_populates="acreditacion")


class CuentaMedicaModelo(Base):
    __tablename__ = "cuenta_medica"

    id: Mapped[int] = mapped_column(primary_key=True)
    identificacion_interna: Mapped[str] = mapped_column(sa.String(10), unique=True, nullable=False)
    asegurado_id: Mapped[int] = mapped_column(sa.ForeignKey("asegurado.id"), nullable=False)
    iafas_id: Mapped[int] = mapped_column(sa.ForeignKey("iafas.id"), nullable=False)
    ipress_id: Mapped[int] = mapped_column(sa.ForeignKey("ipress.id"), nullable=False)
    fecha_prestacion: Mapped[date] = mapped_column(sa.Date, nullable=False)
    hora_prestacion: Mapped[time] = mapped_column(sa.Time, nullable=False)
    # C-05 y RNF-16 (2026-11-13): datos clinicos cifrados en reposo.
    numero_historia_clinica: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    # Codigo CIE10 (T2 campo 18). PROVISIONAL: catalogo oficial CIE-10 del
    # MINSA/REUNIS no disponible (docs/PENDIENTES.md, Fase 4); los valores
    # que carga la Fase 7 son codigos reales de la OMS pero no verificados
    # contra el catalogo aprobado por el MINSA que exige el criterio C2.
    diagnostico_principal_cie10: Mapped[str | None] = mapped_column(TextoCifrado(), nullable=True)
    estado: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="REGISTRADA")
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    asegurado: Mapped[AseguradoModelo] = relationship()
    iafas: Mapped[IafasModelo] = relationship()
    ipress: Mapped[IpressModelo] = relationship()
    acreditacion: Mapped[AcreditacionModelo | None] = relationship(
        back_populates="cuenta", uselist=False
    )
    procedimientos: Mapped[list[ProcedimientoFacturadoModelo]] = relationship(
        back_populates="cuenta", order_by="ProcedimientoFacturadoModelo.id"
    )
    documento: Mapped[DocumentoFacturadorModelo | None] = relationship(
        back_populates="cuenta", uselist=False
    )

    __table_args__ = (
        sa.CheckConstraint(
            "estado IN (" + ",".join(f"'{e}'" for e in ESTADOS_CUENTA_MEDICA) + ")",
            name="ck_cuenta_medica_estado",
        ),
    )


class ProcedimientoFacturadoModelo(Base):
    """Seccion 6.1: descripcion registrada, tipo de clasificacion, codigo
    asignado, version del catalogo, origen del codigo, usuario que confirmo.
    `posicion_aceptada` y `confirmado_en` se agregaron en la Fase 9: la
    Seccion 8.2 tambien exige persistir 'posicion aceptada' e 'instante' de
    la confirmacion, que el modelo de la Fase 7 no tenia porque esta tabla
    todavia no se llenaba desde un flujo real de codificacion."""

    __tablename__ = "procedimiento_facturado"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), nullable=False
    )
    descripcion_registrada: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    tipo_clasificacion: Mapped[str] = mapped_column(sa.String(2), nullable=False, default="01")
    codigo_asignado: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    cpms_version_id: Mapped[int] = mapped_column(sa.ForeignKey("cpms_version.id"), nullable=False)
    origen_codigo: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    # Posicion (1-10) del candidato aceptado en la lista de sugerencias del
    # motor (Seccion 8.2); NULL cuando el origen fue coincidencia exacta
    # por codigo, no una sugerencia.
    posicion_aceptada: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    usuario_confirmo_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuario.id"), nullable=True
    )
    confirmado_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    cantidad: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    monto_unitario: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(sa.Date, nullable=False)
    correlativo: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    cuenta: Mapped[CuentaMedicaModelo] = relationship(back_populates="procedimientos")


class DocumentoFacturadorModelo(Base):
    __tablename__ = "documento_facturador"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    ipress_id: Mapped[int] = mapped_column(sa.ForeignKey("ipress.id"), nullable=False)
    tipo_documento_pago: Mapped[str] = mapped_column(sa.String(2), nullable=False)
    serie: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    numero: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    fecha_emision: Mapped[date] = mapped_column(sa.Date, nullable=False)
    fecha_primer_envio: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    correlativo_prestacion: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    cuenta: Mapped[CuentaMedicaModelo] = relationship(back_populates="documento")

    __table_args__ = (
        # Seccion 6.2: unicidad de (ipress, tipo_documento_pago, serie, numero).
        sa.UniqueConstraint(
            "ipress_id", "tipo_documento_pago", "serie", "numero", name="uq_documento_serie_numero"
        ),
    )


class LoteFacturacionModelo(Base):
    __tablename__ = "lote_facturacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(sa.String(7), nullable=False)
    iafas_id: Mapped[int] = mapped_column(sa.ForeignKey("iafas.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    generado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    # GENERADO (Fase 7) -> CARGADO_VALIDADOR -> OBSERVADO_VALIDADOR o
    # VALIDADO (Fase 16, validacion oficial del simulador TEDEF Web) ->
    # REMITIDO_IAFAS (Fase 8/13, RemitirLote con exito) -> ACEPTADO /
    # RECHAZADO (Fase 12, robot de monitoreo). No es un enumerado cerrado
    # por el plan (a diferencia de cuenta_medica.estado, Seccion 6.3), por
    # eso no lleva CHECK constraint. Hasta la Fase 16 nada produce
    # CARGADO_VALIDADOR/OBSERVADO_VALIDADOR/VALIDADO todavia.
    estado: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="GENERADO")
    # Datos del .S01 obtenido del validador TEDEF Web (Fase 16,
    # RegistrarArchivoTransmision): nulos hasta que el lote llegue a
    # VALIDADO. Reemplazan a las columnas `nombre_archivo_s01` y
    # `huella_sha256` de la version 2, que describian un archivo que el
    # propio backend producia (Regla 11 del plan v3: el backend ya no
    # produce el `.S01`; ver docs/DECISIONES.md, Fase 13).
    nombre_s01: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    sha256_s01: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    ruta_s01: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    s01_obtenido_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    enviado_susalud_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # RT-06: con que version del estandar y del diccionario de mapeo se
    # genero el lote. Nulos en los lotes anteriores a la migracion.
    version_esquema_tedef: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    version_mapeo: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    iafas: Mapped[IafasModelo] = relationship()
    documentos: Mapped[list[LoteDocumentoModelo]] = relationship(back_populates="lote")

    __table_args__ = (
        # Seccion 6.2: unicidad de (iafas, numero_lote).
        sa.UniqueConstraint("iafas_id", "numero", name="uq_lote_iafas_numero"),
    )


class LoteDocumentoModelo(Base):
    __tablename__ = "lote_documento"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        sa.ForeignKey("lote_facturacion.id", ondelete="CASCADE"), nullable=False
    )
    documento_id: Mapped[int] = mapped_column(
        sa.ForeignKey("documento_facturador.id"), nullable=False
    )

    lote: Mapped[LoteFacturacionModelo] = relationship(back_populates="documentos")
    documento: Mapped[DocumentoFacturadorModelo] = relationship()

    __table_args__ = (sa.UniqueConstraint("lote_id", "documento_id", name="uq_lote_documento"),)


class AcuseTransmisionModelo(Base):
    """Seccion 6.1: resultado de la transferencia, respuesta del receptor,
    motivo, instante. Una fila por intento de remision (Seccion 7.8): si la
    transferencia falla, `respuesta_receptor` queda en NULL y un reintento
    posterior crea una fila nueva; si tiene exito, la Fase 12 (robot de
    monitoreo) vuelve a esta misma fila para completar
    `respuesta_receptor`/`motivo_receptor`/`respondido_en` cuando el
    receptor publique su decision."""

    __tablename__ = "acuse_transmision"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        sa.ForeignKey("lote_facturacion.id", ondelete="CASCADE"), nullable=False
    )
    resultado_transferencia: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    motivo_transferencia: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    intentado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    # Completados por el robot de monitoreo (Fase 12), no por RemitirLote.
    respuesta_receptor: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    motivo_receptor: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    respondido_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    lote: Mapped[LoteFacturacionModelo] = relationship()

    __table_args__ = (
        sa.CheckConstraint(
            "resultado_transferencia IN ('ENVIADO','ERROR_TRANSFERENCIA')",
            name="ck_acuse_transmision_resultado_transferencia",
        ),
        sa.CheckConstraint(
            "respuesta_receptor IS NULL OR respuesta_receptor IN ('ACEPTADO','RECHAZADO')",
            name="ck_acuse_transmision_respuesta_receptor",
        ),
    )


class MaestroIafasModelo(Base):
    """Seccion 6.1: tabla maestra para el requisito 8. Sintetica, marcada
    como ficticia (Decision de la Fase 1, supuesto 9)."""

    __tablename__ = "maestro_iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(sa.String(5), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    ficticio: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)


class MaestroIpressModelo(Base):
    __tablename__ = "maestro_ipress"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(sa.String(11), unique=True, nullable=False)
    codigo_ipress: Mapped[str] = mapped_column(sa.String(8), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    ficticio: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)


class EventoModelo(Base):
    """Seccion 6.3 y 6.2.2 (Fase 24), RF-16 y RT-01/RT-12: solo insercion.
    UPDATE, DELETE y TRUNCATE se rechazan por disparador (ver las
    migraciones de la Fase 7 y de esta fase); ademas, la tabla pertenece a
    un rol dueño del esquema distinto de la cuenta de aplicacion, que solo
    tiene INSERT y SELECT (separacion de roles, AD-11).

    `tipo_agregado` + `agregado_id` son el modelo generico de la Tabla 68
    de la tesis (un evento pertenece a la cuenta, al lote, o -- para los
    eventos de sesion que ya existian antes de esta fase y no son
    transiciones del ciclo -- a la sesion de usuario o a la sesion de
    plataforma). `cuenta_medica_id` se conserva, derivado de esas dos
    columnas cuando tipo_agregado='CUENTA', unicamente para no romper las
    consultas de OE1 que ya filtran por ella."""

    __tablename__ = "evento"

    evento_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    tipo_agregado: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    agregado_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cuenta_medica_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), nullable=True
    )
    tipo_evento: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    actor: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    estado_previo: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    estado_nuevo: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    datos: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, default=dict)
    # Control C-07 (Seccion 5.2.7): usuario interno que solicito la
    # operacion, cuando `actor` es el proceso de automatizacion.
    usuario_origen: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    ocurrido_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    version_esquema: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    # Valor resumen con clave (HMAC-SHA256) del evento y del hash_evento
    # del evento anterior del mismo agregado (RNF-18, AD-11); la clave
    # reside fuera de la base (Configuracion.clave_hmac_eventos).
    hash_evento: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "tipo_agregado IN ('CUENTA','LOTE','SESION_USUARIO','SESION_PLATAFORMA')",
            name="ck_evento_tipo_agregado",
        ),
        sa.CheckConstraint("version > 0", name="ck_evento_version_positiva"),
        sa.UniqueConstraint(
            "tipo_agregado", "agregado_id", "version", name="uq_evento_agregado_version"
        ),
    )


class MedicionPasoModelo(Base):
    """Seccion 6.4: una fila por ejecucion, nunca un promedio."""

    __tablename__ = "medicion_paso"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), nullable=True
    )
    lote_id: Mapped[int | None] = mapped_column(sa.ForeignKey("lote_facturacion.id"), nullable=True)
    paso: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    inicio: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    duracion_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    resultado: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, default=dict)


class TrabajoModelo(Base):
    """Seccion 6.1: cola transaccional -- tipo, carga util JSON, estado,
    intentos, proximo_intento, error, instantes. Seccion 6.2: indice sobre
    (estado, proximo_intento). PENDIENTE -> EN_PROCESO -> COMPLETADO, o de
    vuelta a PENDIENTE en cada reintento (Seccion 8.1, punto 6: 'el
    trabajo no se pierde'), o AGOTADO si se supera el maximo configurado.
    REQUIERE_SESION (Seccion 8.4, punto 6, Fase 15): la plataforma externa
    que el trabajo necesita no tiene una sesion asistida ACTIVA; no
    consume intentos y vuelve a PENDIENTE cuando esa sesion se activa."""

    __tablename__ = "trabajo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    carga_util: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    estado: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="PENDIENTE")
    intentos: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    proximo_intento: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    error: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("ix_trabajo_estado_proximo_intento", "estado", "proximo_intento"),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','AGOTADO','REQUIERE_SESION',"
            "'SIN_RESULTADO')",
            name="ck_trabajo_estado",
        ),
    )
