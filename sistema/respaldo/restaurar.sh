#!/bin/bash
# Restauracion de un respaldo cifrado (RNF-19: restauracion en 8 horas).
# Uso: restaurar.sh <respaldo.dump.gpg> <base_destino>
# La base destino se crea vacia; nunca se restaura sobre la base en uso.
set -euo pipefail
# Cifrado autenticado con GnuPG (AES-256 con verificacion de integridad).
# La clave llega por un descriptor, nunca por la linea de ordenes.
export GNUPGHOME="${GNUPGHOME:-/tmp/gnupg}"
mkdir -p "$GNUPGHOME" && chmod 700 "$GNUPGHOME"
export PGHOST="${PGHOST:-postgres}"
archivo="$1"
base="$2"
if [ "$base" = "$POSTGRES_DB" ]; then
  echo "No se restaura sobre la base en uso ($POSTGRES_DB)." >&2
  exit 1
fi
sha256sum -c "${archivo}.sha256"
psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$base\"" -c "CREATE DATABASE \"$base\""
gpg --batch --pinentry-mode loopback --passphrase-fd 3 -d "$archivo" 3< <(printf '%s' "$CLAVE_RESPALDOS") \
  | pg_restore -U "$POSTGRES_USER" -d "$base" --no-owner --exit-on-error
echo "respaldo $archivo restaurado en $base"
