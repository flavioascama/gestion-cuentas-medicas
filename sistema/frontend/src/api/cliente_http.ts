// Unica capa que llama al backend (GUIA_ESTILO_CODIGO.md, Seccion 2.3).
// Los modulos de api/ tipan cada respuesta con los esquemas generados por
// openapi-typescript (components["schemas"][...] de tipos_openapi.ts), sin
// duplicar tipos a mano.

const URL_BASE =
  (import.meta.env.VITE_URL_BASE_API as string | undefined) ?? "http://localhost:8000";
const CLAVE_TOKEN = "oe1_token_sesion";

export class ErrorApi extends Error {
  readonly codigo: string;
  readonly estado_http: number;
  readonly detalles: Record<string, unknown>;

  constructor(
    codigo: string,
    mensaje: string,
    estado_http: number,
    detalles: Record<string, unknown>,
  ) {
    super(mensaje);
    this.codigo = codigo;
    this.estado_http = estado_http;
    this.detalles = detalles;
  }
}

export function guardar_token(token: string): void {
  localStorage.setItem(CLAVE_TOKEN, token);
}

export function borrar_token(): void {
  localStorage.removeItem(CLAVE_TOKEN);
}

export function obtener_token(): string | null {
  return localStorage.getItem(CLAVE_TOKEN);
}

// El backend ya no acepta el token (vencio o fue revocado): quien se
// suscribe (ProveedorSesion) cierra la sesion local y la aplicacion
// vuelve al ingreso, en vez de dejar la pantalla con un mensaje de error.
let _al_expirar_sesion: (() => void) | null = null;

export function suscribir_sesion_expirada(manejador: () => void): () => void {
  _al_expirar_sesion = manejador;
  return () => {
    if (_al_expirar_sesion === manejador) _al_expirar_sesion = null;
  };
}

function construir_query(
  parametros?: Record<string, string | number | boolean | undefined>,
): string {
  if (!parametros) return "";
  const busqueda = new URLSearchParams();
  for (const [clave, valor] of Object.entries(parametros)) {
    if (valor !== undefined) busqueda.set(clave, String(valor));
  }
  const texto = busqueda.toString();
  return texto ? `?${texto}` : "";
}

async function leer_error(respuesta: Response): Promise<ErrorApi> {
  const cuerpo: unknown = await respuesta.json().catch(() => ({}));
  const objeto =
    typeof cuerpo === "object" && cuerpo !== null ? (cuerpo as Record<string, unknown>) : {};
  return new ErrorApi(
    typeof objeto.codigo === "string" ? objeto.codigo : "ERROR_DESCONOCIDO",
    typeof objeto.mensaje === "string" ? objeto.mensaje : "No se pudo completar la operación.",
    respuesta.status,
    typeof objeto.detalles === "object" && objeto.detalles !== null
      ? (objeto.detalles as Record<string, unknown>)
      : {},
  );
}

async function peticion<T>(ruta: string, opciones: RequestInit): Promise<T> {
  const encabezados = new Headers(opciones.headers);
  if (opciones.body !== undefined) encabezados.set("Content-Type", "application/json");
  const token = obtener_token();
  if (token) encabezados.set("Authorization", `Bearer ${token}`);

  const respuesta = await fetch(`${URL_BASE}${ruta}`, { ...opciones, headers: encabezados });
  if (respuesta.status === 401 && token) {
    borrar_token();
    _al_expirar_sesion?.();
  }
  if (!respuesta.ok) throw await leer_error(respuesta);
  if (respuesta.status === 204) return undefined as T;

  const tipo_contenido = respuesta.headers.get("content-type") ?? "";
  if (!tipo_contenido.includes("application/json")) return (await respuesta.blob()) as T;
  return (await respuesta.json()) as T;
}

export function obtener<T>(
  ruta: string,
  parametros?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  return peticion<T>(`${ruta}${construir_query(parametros)}`, { method: "GET" });
}

export function enviar<T>(
  metodo: "POST" | "PUT" | "PATCH" | "DELETE",
  ruta: string,
  cuerpo?: unknown,
): Promise<T> {
  return peticion<T>(ruta, {
    method: metodo,
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
}
