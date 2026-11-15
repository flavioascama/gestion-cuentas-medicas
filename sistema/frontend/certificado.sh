#!/bin/sh
# Certificado del servidor web (C-04): se genera al arrancar si no existe.
# En un despliegue real se monta el certificado emitido por una autoridad.
set -eu
mkdir -p /etc/nginx/tls
if [ ! -f /etc/nginx/tls/servidor.key ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=localhost" \
    -keyout /etc/nginx/tls/servidor.key -out /etc/nginx/tls/servidor.crt
fi
