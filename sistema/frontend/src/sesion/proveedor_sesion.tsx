import { useCallback, useState, type ReactNode } from "react";
import {
  cerrar_sesion as cerrar_sesion_api,
  iniciar_sesion as iniciar_sesion_api,
  obtener_sesion_actual,
  type CargaSesion,
} from "../api/auth";
import { ContextoSesion, type ValorSesion } from "./contexto_sesion";

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, set_sesion] = useState<CargaSesion | null>(() => obtener_sesion_actual());

  const iniciar_sesion = useCallback(async (nombre_usuario: string, clave: string) => {
    await iniciar_sesion_api(nombre_usuario, clave);
    set_sesion(obtener_sesion_actual());
  }, []);

  const cerrar_sesion = useCallback(async () => {
    try {
      await cerrar_sesion_api();
    } catch {
      // El backend pudo rechazar el cierre (token ya vencido, red): el
      // token local ya se borró igual dentro de cerrar_sesion_api (su
      // propio `finally`), así que la sesión del cliente se cierra de
      // todas formas -- nunca debe quedar la persona sin poder salir.
    }
    set_sesion(null);
  }, []);

  const valor: ValorSesion = { sesion, iniciar_sesion, cerrar_sesion };
  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}
