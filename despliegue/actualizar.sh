#!/usr/bin/env bash
# Actualiza el servidor con la ultima version de la rama principal:
#
#   sudo bash despliegue/actualizar.sh
#
# Conserva el .env, los datos y los certificados; solo reconstruye las
# imagenes, aplica las migraciones nuevas y reinicia los servicios.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose)

git pull --ff-only
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d postgres
"${COMPOSE[@]}" run --rm -T backend uv run alembic upgrade head
"${COMPOSE[@]}" up -d
"${COMPOSE[@]}" ps
