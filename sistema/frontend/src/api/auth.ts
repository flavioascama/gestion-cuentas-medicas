import { borrar_token, enviar, guardar_token, obtener_token } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type NombreRol = "analista" | "auditor" | "jefe" | "administrador" | "tesoreria" | "gerente";

export interface CargaSesion {
  usuario_id: number;
  nombre_usuario: string;
  roles: NombreRol[];
  // La contraseña la puso el administrador: hay que cambiarla antes de entrar.
  debe_cambiar_clave: boolean;
}

// El backend firma el JWT (GestorSesionJwt); el frontend solo lee sus
// campos para la interfaz (nombre, rol activo), nunca lo valida -- esa
// autoridad es del backend en cada peticion protegida.
function leer_carga(token: string): Record<string, unknown> | null {
  const partes = token.split(".");
  if (partes.length !== 3 || partes[1] === undefined) return null;
  try {
    const json: unknown = JSON.parse(atob(partes[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof json === "object" && json !== null ? (json as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function decodificar_carga(token: string): CargaSesion | null {
  const carga = leer_carga(token);
  if (
    carga === null ||
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
    debe_cambiar_clave: carga.cambiar_clave === true,
  };
}

export function obtener_sesion_actual(): CargaSesion | null {
  const token = obtener_token();
  return token ? decodificar_carga(token) : null;
}

// Al abrir la aplicacion hay un token guardado cuya fecha de vencimiento
// ya paso. Solo se consulta al cargar, nunca justo despues de ingresar: asi
// un reloj mal puesto en el equipo no impide entrar.
export function hay_sesion_vencida(): boolean {
  const token = obtener_token();
  const carga = token ? leer_carga(token) : null;
  return typeof carga?.exp === "number" && carga.exp * 1000 <= Date.now();
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

// El servidor revoca la credencial con la que se hizo el cambio y entrega
// una nueva.
export async function cambiar_clave(clave_actual: string, clave_nueva: string): Promise<void> {
  const respuesta = await enviar<components["schemas"]["RespuestaInicioSesion"]>(
    "PUT",
    "/auth/clave",
    { clave_actual, clave_nueva },
  );
  guardar_token(respuesta.token);
}

export async function cerrar_sesion(): Promise<void> {
  try {
    await enviar<void>("DELETE", "/auth/sesion");
  } finally {
    borrar_token();
  }
}
