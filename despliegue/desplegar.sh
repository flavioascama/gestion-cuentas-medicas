#!/usr/bin/env bash
# Instala y levanta el sistema completo en un servidor Linux (Ubuntu 22.04 o
# 24.04), desde la raiz del repositorio clonado:
#
#   sudo bash despliegue/desplegar.sh [dominio]
#
# Sin dominio, usa <ip-publica>.sslip.io, un nombre que resuelve a la IP del
# servidor, igual que sus subdominios acredita., iafas. y tedef.
#
# La primera vez instala Docker si falta, genera el .env con claves
# aleatorias (solo en el servidor; nunca se versiona), construye las
# imagenes, aplica las migraciones, carga los catalogos y los datos
# sinteticos y crea el usuario administrador. Volver a ejecutarlo no
# regenera las claves ni vuelve a cargar los datos.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$(pwd)/despliegue/desplegar.sh" "$@"
fi

# Archivos de Compose: el del servidor y, si se indica, ajustes del entorno
# (por ejemplo, .devcontainer/docker-compose.codespaces.yml).
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.nube.yml}"
COMPOSE=(docker compose)

aleatoria() {
  local valor
  valor="$(openssl rand -base64 64 | tr -dc 'A-Za-z0-9')"
  printf '%s' "${valor:0:${1:-32}}"
}
fernet() { openssl rand -base64 32 | tr '+/' '-_'; }
fijar() {
  if grep -q "^$1=" .env; then
    sed -i "s|^$1=.*|$1=$2|" .env
  else
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}

echo "== 1/6 Docker"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "== 2/6 Memoria de intercambio"
# El navegador del robot y la compilacion de las imagenes necesitan mas
# memoria que la de una maquina pequena.
if [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 7000000 ] && [ -z "$(swapon --show)" ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 3/6 Claves del servidor"
if [ ! -f .env ]; then
  DOMINIO="${1:-$(curl -fsS https://api.ipify.org | tr . -).sslip.io}"
  cp .env.ejemplo .env
  chmod 600 .env
  for variable in POSTGRES_PASSWORD CLAVE_FIRMA_SESION CLAVE_HMAC_EVENTOS CLAVE_USUARIO_APLICACION_BD \
    ACREDITA_SALUD_CLAVE FTP_RECEPTOR_IAFAS_CLAVE TEDEF_WEB_CLAVE CORREO_CLAVE CLAVE_BUZON_IAFAS \
    CLAVE_RESPALDOS; do
    fijar "$variable" "$(aleatoria)"
  done
  for variable in CLAVE_CIFRADO_SESIONES CLAVE_CIFRADO_EVIDENCIAS CLAVE_CIFRADO_DATOS; do
    fijar "$variable" "$(fernet)"
  done
  fijar DURACION_SESION_MINUTOS 60
  fijar DOMINIO "$DOMINIO"
  fijar URL_PORTAL_ACREDITA "${URL_PORTAL_ACREDITA:-https://acredita.$DOMINIO}"
  fijar COMPOSE_FILE "$COMPOSE_FILE"
fi
# Clave del simulador del sistema hospitalario: se agrega tambien a un
# despliegue que ya tenia su .env.
if ! grep -q '^SISTEMA_HOSPITALARIO_CLAVE=.' .env; then
  fijar SISTEMA_HOSPITALARIO_CLAVE "$(aleatoria)"
fi
if [ ! -f despliegue/usuarios_simuladores.caddy ]; then
  clave_simuladores="$(aleatoria 20)"
  hash_simuladores="$(docker run --rm caddy:2.8 caddy hash-password --plaintext "$clave_simuladores")"
  printf 'basic_auth {\n\tsimuladores %s\n}\n' "$hash_simuladores" > despliegue/usuarios_simuladores.caddy
  printf 'Portales de los simuladores\nUsuario: simuladores\nClave: %s\n' "$clave_simuladores" \
    > despliegue/acceso_simuladores.txt
  chmod 600 despliegue/acceso_simuladores.txt
fi
DOMINIO="$(grep '^DOMINIO=' .env | cut -d= -f2)"

echo "== 4/6 Imagenes (la primera vez tarda varios minutos)"
"${COMPOSE[@]}" build

echo "== 5/6 Base de datos, catalogos y datos sinteticos"
"${COMPOSE[@]}" up -d postgres
"${COMPOSE[@]}" run --rm -T backend uv run alembic upgrade head
if [ ! -f despliegue/.inicializado ]; then
  for herramienta in cargar_cpms cargar_catalogo_gtin cargar_cie10 cargar_cuentas_sinteticas; do
    "${COMPOSE[@]}" run --rm -T backend uv run python -m "herramientas.$herramienta"
  done
  if [ -n "${ADMIN_CLAVE:-}" ] || { [ -t 0 ] && [ -t 1 ]; }; then
    echo "Usuario administrador 'admin' (clave de al menos 8 caracteres):"
    "${COMPOSE[@]}" run --rm -e ADMIN_CLAVE backend uv run python -m herramientas.crear_usuario_administrador \
      --usuario admin --nombres "Administrador del sistema"
  else
    echo "Crear el administrador con:"
    echo "  sudo ${COMPOSE[*]} run --rm backend uv run python -m herramientas.crear_usuario_administrador --usuario admin --nombres \"Administrador del sistema\""
  fi
  touch despliegue/.inicializado
fi

"${COMPOSE[@]}" run --rm -T backend uv run python -m herramientas.facturar_cuentas_completas

echo "== 6/6 Servicios"
"${COMPOSE[@]}" up -d
bash despliegue/limpiar_imagenes.sh
"${COMPOSE[@]}" ps

echo
echo "Aplicacion: https://$DOMINIO"
if [ -z "${CODESPACE_NAME:-}" ]; then
  echo "Simuladores: https://acredita.$DOMINIO  https://iafas.$DOMINIO  https://tedef.$DOMINIO"
  echo "Acceso a los simuladores: despliegue/acceso_simuladores.txt (solo en este servidor)"
fi
