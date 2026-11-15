# Contexto de build = raiz del repositorio (ver el servicio `trabajador`
# en docker-compose.yml): este Dockerfile necesita copiar tanto
# sistema/backend/ (dependencia de ruta editable, ver pyproject.toml)
# como sistema/automatizacion/, algo que un contexto de
# sistema/automatizacion/ solo no permitiria alcanzar.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY sistema/backend /app/backend
COPY sistema/automatizacion /app/automatizacion

WORKDIR /app/automatizacion
RUN uv sync --no-dev
# --with-deps instala tambien las librerias del sistema operativo que
# Chromium necesita (Debian, via apt) -- sin esto el navegador no arranca
# dentro del contenedor.
RUN uv run playwright install --with-deps chromium

CMD ["uv", "run", "python", "-m", "trabajador.principal"]
