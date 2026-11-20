"""Importa todos los modulos de modelos para que Base.metadata quede
completo en cualquier proceso que lo necesite (scripts de herramientas/,
migraciones, pruebas). SQLAlchemy necesita que TODAS las clases de un
modelo referenciado por una llave foranea esten importadas en el mismo
proceso, aunque la tabla ya exista en la base de datos: sin este modulo,
un script que solo importa `modelos_integracion` (que referencia
`usuario.id`) falla con NoReferencedTableError si nada mas importo
`modelos_acceso` antes.

Uso: `from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401`
al inicio de cualquier script o fixture que arme el esquema completo.
"""

from __future__ import annotations

from app.infraestructura.persistencia import (
    modelos_acceso,  # noqa: F401
    modelos_atencion_hospitalaria,  # noqa: F401
    modelos_carta_garantia,  # noqa: F401
    modelos_catalogo_gtin,  # noqa: F401
    modelos_cie10,  # noqa: F401
    modelos_comunicaciones,  # noqa: F401
    modelos_correos,  # noqa: F401
    modelos_cpms,  # noqa: F401
    modelos_declaracion_susalud,  # noqa: F401
    modelos_documentos_pago,  # noqa: F401
    modelos_farmacia,  # noqa: F401
    modelos_integracion,  # noqa: F401
    modelos_liquidacion,  # noqa: F401
    modelos_observaciones,  # noqa: F401
    modelos_plataformas,  # noqa: F401
    modelos_prevalidacion,  # noqa: F401
    modelos_robot,  # noqa: F401
    proyeccion_ciclo,  # noqa: F401
)
