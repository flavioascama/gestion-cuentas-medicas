"""Atenciones cerradas de la clinica (datos ficticios, fijos, sin azar).

Los pacientes y su aseguradora salen del padron (el mismo de ACREDITA
SALUD); los diagnosticos son codigos del catalogo CIE-10 del MINSA que carga
el sistema (sin punto); los productos de farmacia son del catalogo GTIN del
sistema; los procedimientos se anotan en lenguaje clinico, sin codigo. Las
fechas se calculan respecto del dia de la consulta: siempre son recientes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.padron import PADRON

# El dia de Lima (UTC-5, sin horario de verano): el contenedor corre en UTC
# y date.today() daria el dia siguiente pasadas las 19:00 de Lima.
_ZONA_PERU = timezone(timedelta(hours=-5))


def hoy_peru() -> date:
    return datetime.now(UTC).astimezone(_ZONA_PERU).date()


_PROC = "PROCEDIMIENTO"
_LAB = "LABORATORIO"
_IMG = "IMAGENES"

_CONSULTA_NUEVO = "Consulta ambulatoria para la evaluacion y manejo de un usuario de salud nuevo"
_CONSULTA_CONT = (
    "Consulta ambulatoria especializada para la evaluacion y manejo de un paciente continuador"
)
_ECG = "Electrocardiograma de rutina con por lo menos 12 derivaciones"
_NEBULIZACION = "Tratamiento por inhalacion con nebulizador"
_HIDRATACION = "Infusion intravenosa, hidratacion; inicial, 31 minutos a 1 hora"
_HEMOGRAMA = "Hemograma completo, 3ra generacion"
_COLESTEROL = "Dosaje de colesterol total en sangre completa o suero"
_GLUCOSA = "Dosaje de glucosa en sangre"
_CREATININA = "Dosaje de creatinina en sangre"
_ECO_SUP = "Ecografia abdominal completa superior"
_ECO_INF = "Ecografia abdominal completa inferior"
_RX_TORAX = "Radiografia de torax"
_ANESTESIA = "Anestesia general: primeros 30 minutos"
_CURACION = "Curacion de herida primaria"

# Productos del catalogo GTIN del sistema.
_KETOROLACO = "008400001344"
_MONTELUKAST = "030006030039"
_HIDROCORTISONA = "030900130507"
_VITAMINA_C = "311845319913"
_ZINC = "311845379313"

# Cada atencion: id, tipo, dias atras de la fecha de prestacion (ingreso si
# hay hospitalizacion), hora, historia, documento, medico (colegiatura,
# nombre), diagnostico principal, secundarios, estancia en dias (o None),
# procedimientos (descripcion, area, cantidad, monto, dia de la estancia),
# farmacia (producto, cantidad, monto, dia) y copago (tipo, valor).
_ATENCIONES: list[dict[str, Any]] = [
    {
        "id": "AT-2026-000101",
        "tipo": "AMBULATORIA",
        "atras": 6,
        "hora": "09:15:00",
        "hc": "00045871",
        "doc": "81953443",
        "medico": ("045871", "Luis Paredes Soto"),
        "dx": "J00X",
        "sec": [],
        "estancia": None,
        "proc": [(_CONSULTA_NUEVO, _PROC, 1, "80.00", 0)],
        "farm": [],
        "copago": None,
    },
    {
        "id": "AT-2026-000102",
        "tipo": "AMBULATORIA",
        "atras": 5,
        "hora": "10:30:00",
        "hc": "00051233",
        "doc": "53679371",
        "medico": ("038214", "Carmen Valdivia Rojas"),
        "dx": "K297",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_CONT, _PROC, 1, "120.00", 0),
            (_COLESTEROL, _LAB, 1, "18.00", 0),
            (_HEMOGRAMA, _LAB, 1, "35.00", 0),
            (_ECO_SUP, _IMG, 1, "150.00", 0),
        ],
        "farm": [(_KETOROLACO, 2, "12.50", 0)],
        "copago": None,
    },
    {
        "id": "AT-2026-000103",
        "tipo": "AMBULATORIA",
        "atras": 4,
        "hora": "11:00:00",
        "hc": "00062890",
        "doc": "CE367863",
        "medico": ("052790", "Jorge Quispe Medina"),
        "dx": "M545",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_CONT, _PROC, 1, "120.00", 0),
            ("Radiografia de columna lumbar", _IMG, 1, "90.00", 0),
        ],
        "farm": [(_KETOROLACO, 1, "12.50", 0)],
        "copago": ("fijo", "53.99"),
    },
    {
        "id": "AT-2026-000104",
        "tipo": "AMBULATORIA",
        "atras": 3,
        "hora": "08:45:00",
        "hc": "00071544",
        "doc": "88490756",
        "medico": ("041156", "Rosa Medina Alva"),
        "dx": "N390",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_NUEVO, _PROC, 1, "80.00", 0),
            ("Urocultivo con recuento de colonias cuantitativo", _LAB, 1, "45.00", 0),
            (_CREATININA, _LAB, 1, "15.00", 0),
        ],
        "farm": [(_VITAMINA_C, 1, "9.80", 0)],
        "copago": ("fijo", "57.02"),
    },
    {
        "id": "AT-2026-000105",
        "tipo": "AMBULATORIA",
        "atras": 2,
        "hora": "15:20:00",
        "hc": "00083102",
        "doc": "82022313",
        "medico": ("047332", "Hugo Salazar Prieto"),
        "dx": "J459",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_CONT, _PROC, 1, "120.00", 0),
            (_NEBULIZACION, _PROC, 2, "25.00", 0),
        ],
        "farm": [(_MONTELUKAST, 1, "68.00", 0)],
        "copago": ("pct", "30"),
    },
    {
        "id": "AT-2026-000106",
        "tipo": "AMBULATORIA",
        "atras": 1,
        "hora": "09:50:00",
        "hc": "00094417",
        "doc": "CE931347",
        "medico": ("038214", "Carmen Valdivia Rojas"),
        "dx": "E119",
        "sec": ["I10X"],
        "estancia": None,
        "proc": [
            (_CONSULTA_CONT, _PROC, 1, "120.00", 0),
            (_ECG, _PROC, 1, "60.00", 0),
            (_GLUCOSA, _LAB, 1, "12.00", 0),
            (_COLESTEROL, _LAB, 1, "18.00", 0),
        ],
        "farm": [(_ZINC, 1, "22.00", 0)],
        "copago": None,
    },
    {
        "id": "AT-2026-000107",
        "tipo": "AMBULATORIA",
        "atras": 6,
        "hora": "12:10:00",
        "hc": "00101825",
        "doc": "84804479",
        "medico": ("047332", "Hugo Salazar Prieto"),
        "dx": "E119",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_CONT, _PROC, 1, "120.00", 0),
            (_GLUCOSA, _LAB, 1, "12.00", 0),
        ],
        "farm": [],
        "copago": None,
    },
    {
        "id": "AT-2026-000108",
        "tipo": "AMBULATORIA",
        "atras": 5,
        "hora": "16:00:00",
        "hc": "00112960",
        "doc": "62799687",
        "medico": ("052790", "Jorge Quispe Medina"),
        "dx": "I10X",
        "sec": [],
        "estancia": None,
        "proc": [
            (_CONSULTA_NUEVO, _PROC, 1, "80.00", 0),
            (_ECG, _PROC, 1, "60.00", 0),
        ],
        "farm": [],
        "copago": None,
    },
    {
        "id": "AT-2026-000109",
        "tipo": "EMERGENCIA",
        "atras": 2,
        "hora": "21:40:00",
        "hc": "00123374",
        "doc": "32970220",
        "medico": ("044019", "Andrea Torres Lazo"),
        "dx": "S018",
        "sec": [],
        "estancia": None,
        "proc": [
            ("Sutura simple de heridas superficiales de cuero cabelludo", _PROC, 1, "150.00", 0),
            (_CURACION, _PROC, 1, "40.00", 0),
            ("Tomografia computarizada de craneo sin contraste", _IMG, 1, "420.00", 0),
        ],
        "farm": [(_KETOROLACO, 2, "12.50", 0)],
        "copago": None,
    },
    {
        "id": "AT-2026-000110",
        "tipo": "EMERGENCIA",
        "atras": 1,
        "hora": "02:25:00",
        "hc": "00134508",
        "doc": "54560177",
        "medico": ("044019", "Andrea Torres Lazo"),
        "dx": "A099",
        "sec": [],
        "estancia": None,
        "proc": [
            (_HIDRATACION, _PROC, 1, "70.00", 0),
            (_HEMOGRAMA, _LAB, 1, "35.00", 0),
        ],
        "farm": [(_ZINC, 1, "22.00", 0)],
        "copago": None,
    },
    {
        "id": "AT-2026-000111",
        "tipo": "EMERGENCIA",
        "atras": 3,
        "hora": "23:05:00",
        "hc": "00145226",
        "doc": "CE267554",
        "medico": ("049581", "Pablo Cardenas Ruiz"),
        "dx": "J459",
        "sec": [],
        "estancia": None,
        "proc": [
            (_NEBULIZACION, _PROC, 3, "25.00", 0),
            (_RX_TORAX, _IMG, 1, "85.00", 0),
        ],
        "farm": [(_HIDROCORTISONA, 1, "45.00", 0), (_MONTELUKAST, 1, "68.00", 0)],
        "copago": ("pct", "20"),
    },
    {
        "id": "AT-2026-000112",
        "tipo": "HOSPITALIZACION",
        "atras": 6,
        "hora": "07:30:00",
        "hc": "00156739",
        "doc": "21396432",
        "medico": ("041156", "Rosa Medina Alva"),
        "dx": "K359",
        "sec": ["E669"],
        "estancia": 3,
        "proc": [
            ("Apendicectomia", _PROC, 1, "2800.00", 0),
            (_ANESTESIA, _PROC, 3, "250.00", 0),
            (_CURACION, _PROC, 3, "40.00", 1),
            (_HEMOGRAMA, _LAB, 2, "35.00", 0),
            (_CREATININA, _LAB, 1, "15.00", 0),
            (_GLUCOSA, _LAB, 2, "12.00", 0),
            (_ECO_INF, _IMG, 1, "150.00", 0),
            (_ECO_SUP, _IMG, 1, "150.00", 0),
        ],
        "farm": [(_KETOROLACO, 6, "12.50", 0), (_HIDROCORTISONA, 2, "45.00", 1)],
        "copago": None,
    },
    {
        "id": "AT-2026-000113",
        "tipo": "HOSPITALIZACION",
        "atras": 7,
        "hora": "18:15:00",
        "hc": "00167045",
        "doc": "CE204107",
        "medico": ("049581", "Pablo Cardenas Ruiz"),
        "dx": "J189",
        "sec": ["E119", "I10X"],
        "estancia": 5,
        "proc": [
            (_NEBULIZACION, _PROC, 6, "25.00", 1),
            (_ECG, _PROC, 1, "60.00", 0),
            (_HIDRATACION, _PROC, 4, "70.00", 1),
            (_HEMOGRAMA, _LAB, 3, "35.00", 0),
            (_GLUCOSA, _LAB, 5, "12.00", 0),
            (_CREATININA, _LAB, 2, "15.00", 0),
            (_RX_TORAX, _IMG, 2, "85.00", 0),
            ("Tomografia computarizada de torax sin contraste", _IMG, 1, "480.00", 2),
        ],
        "farm": [
            (_HIDROCORTISONA, 4, "45.00", 0),
            (_KETOROLACO, 5, "12.50", 0),
            (_MONTELUKAST, 2, "68.00", 2),
        ],
        "copago": ("fijo", "33.50"),
    },
    {
        "id": "AT-2026-000114",
        "tipo": "HOSPITALIZACION",
        "atras": 5,
        "hora": "13:20:00",
        "hc": "00178362",
        "doc": "PA184172",
        "medico": ("041156", "Rosa Medina Alva"),
        "dx": "K810",
        "sec": ["I10X"],
        "estancia": 3,
        "proc": [
            ("Colecistectomia", _PROC, 1, "3200.00", 1),
            (_ANESTESIA, _PROC, 4, "250.00", 1),
            (_CURACION, _PROC, 2, "40.00", 2),
            (_HEMOGRAMA, _LAB, 2, "35.00", 0),
            (_CREATININA, _LAB, 1, "15.00", 0),
            (_GLUCOSA, _LAB, 1, "12.00", 0),
            (_ECO_SUP, _IMG, 1, "150.00", 0),
        ],
        "farm": [(_KETOROLACO, 6, "12.50", 1), (_VITAMINA_C, 2, "9.80", 2)],
        "copago": ("pct", "30"),
    },
]


def _dinero(valor: Decimal) -> str:
    return str(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def total_atencion(atencion: dict[str, Any]) -> Decimal:
    total = Decimal(0)
    for p in atencion["procedimientos"]:
        total += Decimal(p["monto_unitario"]) * p["cantidad"]
    for f in atencion["farmacia"]:
        total += Decimal(f["monto_unitario"]) * Decimal(f["cantidad"])
    return total


def _construir_copago(
    atencion: dict[str, Any], fecha: date, total: Decimal
) -> dict[str, str] | None:
    if atencion["copago"] is None:
        return None
    clase, valor = atencion["copago"]
    monto = Decimal(valor)
    if clase == "pct":
        monto = total * monto / Decimal(100)
    return {
        "monto": _dinero(monto),
        "referencia": f"B001-{atencion['id'][-6:]}",
        "fecha": fecha.isoformat(),
    }


def _construir(atencion: dict[str, Any], hoy: date) -> dict[str, Any]:
    inicio = hoy - timedelta(days=atencion["atras"])
    estancia = atencion["estancia"]
    alta = inicio + timedelta(days=estancia) if estancia else inicio
    tipo_doc, nombres, apellidos, iafas = PADRON[atencion["doc"]]
    colegiatura, medico = atencion["medico"]
    completa: dict[str, Any] = {
        "atencion_id": atencion["id"],
        "tipo_atencion": atencion["tipo"],
        "fecha_prestacion": inicio.isoformat(),
        "hora_prestacion": atencion["hora"],
        "numero_historia_clinica": atencion["hc"],
        "paciente": {
            "tipo_documento": tipo_doc,
            "numero_documento": atencion["doc"],
            "nombres": nombres,
            "apellidos": apellidos,
        },
        "iafas_codigo": iafas,
        "profesional": {"numero_colegiatura": colegiatura, "nombres": medico},
        "diagnostico_principal_cie10": atencion["dx"],
        "diagnosticos_secundarios_cie10": list(atencion["sec"]),
        "hospitalizacion": (
            {"fecha_ingreso": inicio.isoformat(), "fecha_alta": alta.isoformat()}
            if estancia
            else None
        ),
        "procedimientos": [
            {
                "descripcion": descripcion,
                "area": area,
                "cantidad": cantidad,
                "monto_unitario": monto,
                "fecha": (inicio + timedelta(days=dia)).isoformat(),
            }
            for descripcion, area, cantidad, monto, dia in atencion["proc"]
        ],
        "farmacia": [
            {
                "codigo_producto": producto,
                "cantidad": str(cantidad),
                "tipo_unidad_dispensacion": "1",
                "monto_unitario": monto,
                "fecha_dispensacion": (inicio + timedelta(days=dia)).isoformat(),
            }
            for producto, cantidad, monto, dia in atencion["farm"]
        ],
    }
    completa["copago_cobrado"] = _construir_copago(atencion, alta, total_atencion(completa))
    return completa


def todas_las_atenciones(hoy: date | None = None) -> list[dict[str, Any]]:
    dia = hoy or hoy_peru()
    return [_construir(a, dia) for a in _ATENCIONES]
