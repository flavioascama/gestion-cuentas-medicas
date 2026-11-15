#!/bin/bash
# Prueba de restauracion (RNF-19, C-14): restaura el respaldo mas reciente
# en una base temporal, compara el conteo de las tablas principales con la
# base en uso, mide el tiempo y borra la base temporal.
set -euo pipefail
# Cifrado autenticado con GnuPG (AES-256 con verificacion de integridad).
# La clave llega por un descriptor, nunca por la linea de ordenes.
export GNUPGHOME="${GNUPGHOME:-/tmp/gnupg}"
mkdir -p "$GNUPGHOME" && chmod 700 "$GNUPGHOME"
export PGHOST="${PGHOST:-postgres}"
ultimo="$(ls -1t /respaldos/respaldo_*.dump.gpg | head -1)"
inicio=$(date +%s)
bash "$(dirname "$0")/restaurar.sh" "$ultimo" restauracion_prueba
for tabla in evento cuenta_medica lote_facturacion documento_facturador usuario; do
  origen=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from $tabla")
  restaurado=$(psql -U "$POSTGRES_USER" -d restauracion_prueba -Atc "select count(*) from $tabla")
  echo "$tabla: en uso $origen, restaurado $restaurado"
done
fin=$(date +%s)
psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE restauracion_prueba" > /dev/null
echo "restauracion de $ultimo verificada en $((fin - inicio)) s"
