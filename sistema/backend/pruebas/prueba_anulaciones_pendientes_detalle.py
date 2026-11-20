"""La bandeja de anulaciones pendientes muestra lo que se anula
(2026-11-19): estado de la cuenta, comprobante vigente y nota de credito."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.dominio.cierre.casos_uso import ListarSolicitudesAnulacionPendientes
from app.dominio.cierre.valores import EstadoSolicitudAnulacion, SolicitudAnulacion
from app.dominio.pse.documentos import ComprobanteVigente, DocumentosPagoCuenta, NotaDocumento

_AHORA = datetime(2026, 11, 19, 9, 0, 0)


def _solicitud(cuenta_id: int) -> SolicitudAnulacion:
    return SolicitudAnulacion(
        id=cuenta_id,
        cuenta_medica_id=cuenta_id,
        motivo="Duplicada",
        estado=EstadoSolicitudAnulacion.PENDIENTE,
        solicitado_por="ana",
        solicitado_en=_AHORA,
        resuelto_por=None,
        resuelto_en=None,
        estado_cuenta="FACTURADA",
    )


def _nota(tipo: str) -> NotaDocumento:
    return NotaDocumento(
        tipo=tipo,
        serie="FC01",
        numero="00000007",
        monto=Decimal("50.00"),
        fecha=date(2026, 11, 18),
        motivo="A",
        registrado_en=_AHORA,
        registrado_por="ana",
    )


@dataclass
class _Solicitudes:
    async def listar_pendientes(self) -> list[SolicitudAnulacion]:
        return [_solicitud(1), _solicitud(2), _solicitud(3)]


class _Documentos:
    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        if cuenta_medica_id == 3:
            return None
        vigente = ComprobanteVigente(
            documento_id=cuenta_medica_id,
            tipo_documento_pago="01",
            serie="F001",
            numero=f"0000012{cuenta_medica_id}",
            fecha_emision=date(2026, 11, 1),
        )
        nota = _nota("C") if cuenta_medica_id == 1 else _nota("D")
        return DocumentosPagoCuenta(vigente=vigente, nota=nota)


async def prueba_cada_solicitud_lleva_comprobante_vigente_y_nota_de_credito() -> None:
    caso_uso = ListarSolicitudesAnulacionPendientes(
        _Solicitudes(),  # type: ignore[arg-type]
        _Documentos(),  # type: ignore[arg-type]
    )

    con_nota, con_debito, sin_comprobante = await caso_uso.ejecutar()

    assert (con_nota.estado_cuenta, con_nota.comprobante, con_nota.nota_credito) == (
        "FACTURADA",
        "F001-00000121",
        "FC01-00000007",
    )
    # Una nota de debito no es una nota de credito.
    assert (con_debito.comprobante, con_debito.nota_credito) == ("F001-00000122", None)
    assert (sin_comprobante.comprobante, sin_comprobante.nota_credito) == (None, None)


async def prueba_sin_documentos_la_bandeja_no_cambia() -> None:
    solicitudes = await ListarSolicitudesAnulacionPendientes(
        _Solicitudes()  # type: ignore[arg-type]
    ).ejecutar()

    assert [s.comprobante for s in solicitudes] == [None, None, None]
