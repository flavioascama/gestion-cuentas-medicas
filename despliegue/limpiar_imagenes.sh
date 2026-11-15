#!/usr/bin/env bash
# Libera el disco que dejan las reconstrucciones: borra las versiones
# anteriores de las imagenes (las que ya no usa ningun servicio) y la
# cache de construccion sin usar en las ultimas 24 horas. No toca los
# datos de la base ni los contenedores en ejecucion. Si algo falla, el
# despliegue continua.
set -uo pipefail

echo "== Limpieza de versiones anteriores"
docker image prune -f | tail -n 1 || true
docker builder prune -f --filter until=24h | tail -n 1 || true
