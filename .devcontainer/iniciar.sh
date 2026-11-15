#!/usr/bin/env bash
# Levanta el sistema cada vez que inicia el codespace.
set -euo pipefail
cd "$(dirname "$0")/.."

base="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
export COMPOSE_FILE="docker-compose.nube.yml:.devcontainer/docker-compose.codespaces.yml"
export URL_PORTAL_ACREDITA="https://${CODESPACE_NAME}-8100.${base}"

for _ in $(seq 1 60); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done

bash despliegue/desplegar.sh "${CODESPACE_NAME}-8443.${base}" 2>&1 | tee "$HOME/iniciar.log"
