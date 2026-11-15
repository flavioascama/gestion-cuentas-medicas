import { useState } from "react";
import type { NombreRol } from "../../api/auth";
import type { Usuario } from "../../api/usuarios";

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

export function usar_formulario_usuario(usuario: Usuario | null) {
  const es_edicion = usuario !== null;
  const [nombre_usuario, set_nombre_usuario] = useState(usuario?.nombre_usuario ?? "");
  const [nombres, set_nombres] = useState(usuario?.nombres ?? "");
  const [clave, set_clave] = useState("");
  const [roles, set_roles] = useState<Set<NombreRol>>(new Set(usuario?.roles ?? []));

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
