// Mapa unico de roles (mismo criterio que mapa_estados.ts): un solo
// lugar que traduce el nombre de rol que devuelve el backend
// (NombreRol, snake_case en espanol salvo "tesoreria"/"gerente", que el
// API nunca capitalizo) a su etiqueta visible. Antes de este mapa,
// barra_lateral.tsx mostraba los roles crudos del token
// (roles.join(", ")) y seccion_usuarios.tsx tenia su propia copia
// incompleta (sin tesoreria/gerente, agregados recien en la Fase 25) --
// un usuario con esos roles se veia inconsistente entre la tarjeta de
// perfil y la tabla de administracion.

const _ETIQUETAS_ROL: Record<string, string> = {
  analista: "Analista",
  auditor: "Auditor",
  jefe: "Jefe",
  tesoreria: "Tesorería",
  gerente: "Gerente",
  administrador: "Administrador",
};

export function etiqueta_rol(rol: string): string {
  return _ETIQUETAS_ROL[rol] ?? rol;
}

// La pantalla trabaja con cuatro perfiles; el perfil Jefe reune los roles
// jefe, tesoreria y gerente del servidor. Esta es la unica fuente de la regla.
const _ROLES_DEL_PERFIL_JEFE = ["jefe", "tesoreria", "gerente"];

// Roles del servidor -> perfiles: quien tiene los tres roles del perfil Jefe
// se ve como "jefe"; tesoreria o gerente sueltos conservan su propio rol.
export function perfiles_de_roles<T extends string>(roles: readonly T[]): T[] {
  const completo = _ROLES_DEL_PERFIL_JEFE.every((rol) =>
    (roles as readonly string[]).includes(rol),
  );
  if (!completo) return [...roles];
  return roles.filter((rol) => rol === "jefe" || !_ROLES_DEL_PERFIL_JEFE.includes(rol));
}

// Perfiles -> roles del servidor: marcar Jefe envia tambien tesoreria y gerente.
export function roles_de_perfiles<T extends string>(perfiles: readonly T[]): T[] {
  const roles = new Set<string>(perfiles);
  if (roles.has("jefe")) _ROLES_DEL_PERFIL_JEFE.forEach((rol) => roles.add(rol));
  return Array.from(roles) as T[];
}

export function etiquetas_roles(roles: string[]): string {
  return perfiles_de_roles(roles).map(etiqueta_rol).join(", ");
}
