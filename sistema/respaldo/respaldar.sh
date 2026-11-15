#!/bin/bash
# Respaldo diario cifrado de la base (RNF-19, C-14, AD-13, RAS-12): pg_dump en
# formato propio, cifrado con CLAVE_RESPALDOS, con su huella SHA-256, y
# retencion de RESPALDO_RETENCION_DIAS dias. Lo corre el servicio `respaldo`.
set -euo pipefail
# Cifrado autenticado con GnuPG (AES-256 con verificacion de integridad).
# La clave llega por un descriptor, nunca por la linea de ordenes.
export GNUPGHOME="${GNUPGHOME:-/tmp/gnupg}"
mkdir -p "$GNUPGHOME" && chmod 700 "$GNUPGHOME"
export PGHOST="${PGHOST:-postgres}"
intervalo=$(( ${RESPALDO_INTERVALO_HORAS:-24} * 3600 ))
retencion="${RESPALDO_RETENCION_DIAS:-30}"
mkdir -p /respaldos

respaldar() {
  local marca destino
  marca="$(date -u +%Y%m%dT%H%M%SZ)"
  destino="/respaldos/respaldo_${marca}.dump.gpg"
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
    | gpg --batch --yes --pinentry-mode loopback --symmetric --cipher-algo AES256 \
        --passphrase-fd 3 -o "${destino}.parcial" 3< <(printf '%s' "$CLAVE_RESPALDOS")
  mv "${destino}.parcial" "$destino"
  sha256sum "$destino" > "${destino}.sha256"
  find /respaldos -name 'respaldo_*' -mtime +"$retencion" -delete
  echo "[$marca] respaldo ${destino} ($(stat -c %s "$destino") bytes)"
}

while true; do
  respaldar || echo "[$(date -u +%Y%m%dT%H%M%SZ)] respaldo FALLIDO"
  sleep "$intervalo"
done
