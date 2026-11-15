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

export function etiquetas_roles(roles: string[]): string {
  return roles.map(etiqueta_rol).join(", ");
}
