# RNF-14 y AD-08: la aplicacion web tambien corre en su propio contenedor.
# Etapa 1: compila con Vite. Las VITE_* se fijan al compilar (Vite las
# incrusta en el paquete), por eso llegan como argumentos de construccion.
FROM node:22-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_URL_BASE_API=/api
ARG VITE_URL_PORTAL_ACREDITA_SALUD=http://localhost:8100
ARG VITE_INTERVALO_REFRESCO_PANEL_SEGUNDOS=60
ENV VITE_URL_BASE_API=$VITE_URL_BASE_API \
    VITE_URL_PORTAL_ACREDITA_SALUD=$VITE_URL_PORTAL_ACREDITA_SALUD \
    VITE_INTERVALO_REFRESCO_PANEL_SEGUNDOS=$VITE_INTERVALO_REFRESCO_PANEL_SEGUNDOS
RUN npm run build

# Etapa 2: sirve los archivos estaticos; cualquier ruta de la aplicacion
# (React Router) devuelve index.html.
FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
# La imagen de nginx sustituye las variables de las plantillas al arrancar
# y corre los scripts de /docker-entrypoint.d (aqui, el certificado).
COPY plantillas/default.conf.template /etc/nginx/templates/default.conf.template
COPY certificado.sh /docker-entrypoint.d/05-certificado.sh
RUN chmod +x /docker-entrypoint.d/05-certificado.sh
COPY --from=compilacion /app/dist /usr/share/nginx/html
EXPOSE 80 443
