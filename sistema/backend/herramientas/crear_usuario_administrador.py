"""Crea el primer usuario administrador. Idempotente: si ya existe, no falla.

No hay otra via para obtener el primer usuario del sistema, ya que crear
usuarios (CU-18) requiere ya estar autenticado como administrador. Requiere
que la migracion que siembra los cuatro roles ya se haya aplicado.

Uso:
    uv run python herramientas/crear_usuario_administrador.py \
        --usuario admin --nombres "Nombre Apellido"

La clave se lee de la variable de entorno ADMIN_CLAVE o, si no esta
definida, se pide de forma interactiva (nunca por argumento de linea de
comandos, para no dejarla en el historial del shell).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.errores import ClaveDebilError, NombreUsuarioDuplicadoError
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt


async def crear(nombre_usuario: str, clave: str, nombres: str) -> None:
    async with FabricaSesiones() as sesion:
        repositorio = RepositorioUsuariosSql(sesion)
        caso_uso = RegistrarUsuario(repositorio, VerificadorClaveBcrypt())
        try:
            usuario = await caso_uso.ejecutar(
                nombre_usuario=nombre_usuario,
                clave=clave,
                nombres=nombres,
                roles=frozenset({NombreRol.ADMINISTRADOR}),
            )
        except NombreUsuarioDuplicadoError:
            print(f"El usuario '{nombre_usuario}' ya existe; no se crea de nuevo.")
            return
        except ClaveDebilError as error:
            # Control C-01 (Seccion 5.2.7): RegistrarUsuario ya la exige;
            # este mensaje solo evita que quien corre el script a mano
            # tenga que leer la traza para enterarse de por que fallo.
            sys.exit(str(error))
    print(f"Usuario administrador '{usuario.nombre_usuario}' creado (id={usuario.id}).")


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--usuario", required=True, help="nombre_usuario de acceso")
    analizador.add_argument("--nombres", required=True, help="nombres completos, para mostrar")
    argumentos = analizador.parse_args()

    clave = os.environ.get("ADMIN_CLAVE") or getpass.getpass("Clave del administrador: ")

    asyncio.run(crear(argumentos.usuario, clave, argumentos.nombres))


if __name__ == "__main__":
    main()
