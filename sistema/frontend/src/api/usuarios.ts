import { enviar, obtener } from "./cliente_http";
import type { NombreRol } from "./auth";
import type { components } from "./tipos_openapi";

export type Usuario = components["schemas"]["RespuestaUsuario"];

export interface SolicitudCrearUsuario {
  nombre_usuario: string;
  clave: string;
  nombres: string;
  roles: NombreRol[];
}

export interface SolicitudActualizarUsuario {
  nombres?: string;
  roles?: NombreRol[];
  activo?: boolean;
}

export function listar_usuarios(): Promise<Usuario[]> {
  return obtener<Usuario[]>("/usuarios");
}

export function crear_usuario(solicitud: SolicitudCrearUsuario): Promise<Usuario> {
  return enviar<Usuario>("POST", "/usuarios", solicitud);
}

export function restablecer_clave_usuario(usuario_id: number, clave: string): Promise<Usuario> {
  return enviar<Usuario>("POST", `/usuarios/${usuario_id}/restablecer-clave`, { clave });
}

export function actualizar_usuario(
  usuario_id: number,
  solicitud: SolicitudActualizarUsuario,
): Promise<Usuario> {
  return enviar<Usuario>("PATCH", `/usuarios/${usuario_id}`, solicitud);
}

// Solo se elimina el usuario que nunca tuvo actividad en el sistema.
export function eliminar_usuario(usuario_id: number): Promise<void> {
  return enviar<void>("DELETE", `/usuarios/${usuario_id}`);
}
