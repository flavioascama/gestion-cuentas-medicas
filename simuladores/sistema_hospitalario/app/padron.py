"""Padron de pacientes de la clinica: los mismos asegurados (documento, nombres,
aseguradora) que conoce el simulador de ACREDITA SALUD
(simuladores/datos_semilla/asegurados.json), copiados aqui para que este
simulador no dependa de archivos fuera de su carpeta."""

from __future__ import annotations

# numero_documento -> (tipo_documento, nombres, apellidos, iafas_codigo)
PADRON: dict[str, tuple[str, str, str, str]] = {
    "81953443": ("1", "Elvira", "Ochoa Cañas", "99553"),
    "53679371": ("1", "Nydia", "Sarmiento Acosta", "05292"),
    "21396432": ("1", "Matilde", "Iniesta Cánovas", "99553"),
    "CE931347": ("2", "Atilio", "Salinas Plaza", "19395"),
    "CE367863": ("2", "Benigno", "Macías Oliveras", "05292"),
    "88490756": ("1", "Zacarías", "Larrea Heredia", "19395"),
    "82022313": ("1", "Agustina", "Prats Mir", "99553"),
    "CE267554": ("2", "Timoteo", "Tomás Cañizares", "19395"),
    "84804479": ("1", "Loreto", "Terrón Gallardo", "19395"),
    "62799687": ("1", "Eli", "Delgado Bellido", "05292"),
    "32970220": ("1", "Asdrubal", "Manjón Cabrera", "19395"),
    "54560177": ("1", "Cristian", "Company Vidal", "99553"),
    "CE204107": ("2", "Plácido", "Sánchez Buendía", "05292"),
    "PA184172": ("3", "Pía", "Hurtado Montes", "05292"),
}
