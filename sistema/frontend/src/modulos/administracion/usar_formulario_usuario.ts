import { useState } from "react";
import type { NombreRol } from "../../api/auth";
import type { Usuario } from "../../api/usuarios";
import { perfiles_de_roles } from "../../componentes_base/mapa_roles";
import { usar_sesion } from "../../sesion/contexto_sesion";

function falta_completar_creacion(
  nombre_usuario: string,
  clave: string,
  nombres: string,
  cantidad_roles: number,
): boolean {
  return (
    nombre_usuario.trim().length < 3 ||
    clave.length < 8 ||
    nombres.trim().length === 0 ||
    cantidad_roles === 0
  );
}

// El usuario de la sesion no cambia sus propios roles.
function usar_es_propio(usuario: Usuario | null): boolean {
  const { sesion } = usar_sesion();
  return usuario !== null && sesion?.usuario_id === usuario.id;
}

export function usar_formulario_usuario(usuario: Usuario | null) {
  const es_edicion = usuario !== null;
  const es_propio = usar_es_propio(usuario);
  const [nombre_usuario, set_nombre_usuario] = useState(usuario?.nombre_usuario ?? "");
  const [nombres, set_nombres] = useState(usuario?.nombres ?? "");
  const [clave, set_clave] = useState("");
  const [roles, set_roles] = useState<Set<NombreRol>>(
    new Set(perfiles_de_roles(usuario?.roles ?? [])),
  );

  const alternar_rol = (rol: NombreRol) => {
    set_roles((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(rol)) nuevo.delete(rol);
      else nuevo.add(rol);
      return nuevo;
    });
  };

  const falta_completar = es_edicion
    ? nombres.trim().length === 0 || roles.size === 0
    : falta_completar_creacion(nombre_usuario, clave, nombres, roles.size);

  return {
    es_edicion,
    es_propio,
    nombre_usuario,
    set_nombre_usuario,
    nombres,
    set_nombres,
    clave,
    set_clave,
    roles,
    alternar_rol,
    falta_completar,
  };
}
