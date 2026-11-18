import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  cambiar_clave as cambiar_clave_api,
  cerrar_sesion as cerrar_sesion_api,
  hay_sesion_vencida,
  iniciar_sesion as iniciar_sesion_api,
  obtener_sesion_actual,
  type CargaSesion,
} from "../api/auth";
import { borrar_token, suscribir_sesion_expirada } from "../api/cliente_http";
import { olvidar_estados_de_sesion } from "../utilidades/estado_de_sesion";
import { ContextoSesion, type ValorSesion } from "./contexto_sesion";

export function ProveedorSesion({ children }: { children: ReactNode }) {
  // Un token guardado que ya vencio no es una sesion: se entra directo al
  // ingreso, sin pasar por una pantalla que el backend va a rechazar. El
  // ingreso no avisa nada (pedido del usuario, 2026-11-18).
  const [vencida_al_cargar] = useState(hay_sesion_vencida);
  const [sesion, set_sesion] = useState<CargaSesion | null>(() =>
    vencida_al_cargar ? null : obtener_sesion_actual(),
  );

  useEffect(() => {
    if (vencida_al_cargar) borrar_token();
  }, [vencida_al_cargar]);

  // El backend rechazo el token en plena sesion (vencio o fue revocado): se
  // cierra la sesion local y RutaProtegida lleva al ingreso.
  useEffect(
    () =>
      suscribir_sesion_expirada(() => {
        olvidar_estados_de_sesion();
        set_sesion(null);
      }),
    [],
  );

  const iniciar_sesion = useCallback(async (nombre_usuario: string, clave: string) => {
    await iniciar_sesion_api(nombre_usuario, clave);
    // Quien entra no hereda los filtros de quien uso antes la pestana.
    olvidar_estados_de_sesion();
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
    olvidar_estados_de_sesion();
    set_sesion(null);
  }, []);

  const cambiar_clave = useCallback(async (clave_actual: string, clave_nueva: string) => {
    await cambiar_clave_api(clave_actual, clave_nueva);
    set_sesion(obtener_sesion_actual());
  }, []);

  const valor: ValorSesion = { sesion, iniciar_sesion, cerrar_sesion, cambiar_clave };
  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}
