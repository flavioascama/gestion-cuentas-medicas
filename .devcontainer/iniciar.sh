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

bash despliegue/desplegar.sh "${CODESPACE_NAME}-8443.${base}" < /dev/null 2>&1 | tee "$HOME/iniciar.log"

# El enlace de la aplicacion debe ser publico: en privado, Codespaces reenvia
# el puerto 8443 por HTTPS y el proxy responde por HTTP. La visibilidad vuelve
# a privado en cada arranque, por eso se fija aqui. Los portales de los
# simuladores quedan privados.
publicar_aplicacion() {
  if ! command -v gh >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gh || return 1
  fi
  for _ in $(seq 1 10); do
    gh codespace ports visibility 8443:public -c "$CODESPACE_NAME" && return 0
    sleep 6
  done
  return 1
}
if publicar_aplicacion >> "$HOME/iniciar.log" 2>&1; then
  echo "Enlace de la aplicacion: publico"
else
  echo "No se pudo publicar el puerto 8443: hacerlo desde la pestana Puertos."
fi
