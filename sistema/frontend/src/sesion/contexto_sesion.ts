import { createContext, useContext } from "react";
import type { CargaSesion } from "../api/auth";

export interface ValorSesion {
  sesion: CargaSesion | null;
  // La sesion anterior se cerro sola porque vencio: el ingreso lo dice.
  sesion_vencida: boolean;
  iniciar_sesion: (nombre_usuario: string, clave: string) => Promise<void>;
  cerrar_sesion: () => Promise<void>;
}

export const ContextoSesion = createContext<ValorSesion | null>(null);

export function usar_sesion(): ValorSesion {
  const contexto = useContext(ContextoSesion);
  if (contexto === null) throw new Error("usar_sesion debe usarse dentro de ProveedorSesion.");
  return contexto;
}
