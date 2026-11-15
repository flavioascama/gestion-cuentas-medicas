import { borrar_token, enviar, guardar_token, obtener_token } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type NombreRol = "analista" | "auditor" | "jefe" | "administrador" | "tesoreria" | "gerente";

export interface CargaSesion {
  usuario_id: number;
  nombre_usuario: string;
  roles: NombreRol[];
}

// El backend firma el JWT (GestorSesionJwt); el frontend solo lee sus
// campos para la interfaz (nombre, rol activo), nunca lo valida -- esa
// autoridad es del backend en cada peticion protegida.
function decodificar_carga(token: string): CargaSesion | null {
  const partes = token.split(".");
  if (partes.length !== 3 || partes[1] === undefined) return null;
  try {
    const json: unknown = JSON.parse(atob(partes[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (typeof json !== "object" || json === null) return null;
    const carga = json as Record<string, unknown>;
    if (
      typeof carga.sub !== "string" ||
      typeof carga.nombre_usuario !== "string" ||
      !Array.isArray(carga.roles)
    ) {
      return null;
    }
    return {
      usuario_id: Number(carga.sub),
      nombre_usuario: carga.nombre_usuario,
      roles: carga.roles as NombreRol[],
    };
  } catch {
    return null;
  }
}

export function obtener_sesion_actual(): CargaSesion | null {
  const token = obtener_token();
  return token ? decodificar_carga(token) : null;
}

export async function iniciar_sesion(
  nombre_usuario: string,
  clave: string,
): Promise<components["schemas"]["RespuestaInicioSesion"]> {
  const respuesta = await enviar<components["schemas"]["RespuestaInicioSesion"]>(
    "POST",
    "/auth/sesion",
    {
      nombre_usuario,
      clave,
    },
  );
  guardar_token(respuesta.token);
  return respuesta;
}

export async function cerrar_sesion(): Promise<void> {
  try {
    await enviar<void>("DELETE", "/auth/sesion");
  } finally {
    borrar_token();
  }
}
