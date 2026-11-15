from __future__ import annotations

import uvicorn

from app.almacenamiento import AlmacenamientoPse
from app.configuracion import configuracion
from app.portal_web import construir_app


def main() -> None:
    almacenamiento = AlmacenamientoPse(configuracion.base_datos)
    app = construir_app(almacenamiento)
    uvicorn.run(app, host="0.0.0.0", port=configuracion.portal_puerto)


if __name__ == "__main__":
    main()
