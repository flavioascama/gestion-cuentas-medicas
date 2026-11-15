import type { NavigateFunction } from "react-router-dom";
import type { MigaPan } from "../componentes_base/migas_pan";

// Contexto de navegacion (rediseno del 2026-11-12, pedido del usuario): al
// abrir una cuenta desde un aviso o desde un lote, la pantalla de destino
// sabe de donde se vino, como volver y cual es el elemento anterior y el
// siguiente de esa misma lista. Viaja en el `state` de React Router (no en
// la URL): si se recarga la pagina o se entra por un enlace directo, el
// detalle se ve como siempre, con sus migas por defecto.

export interface PasoRecorrido {
  ruta: string;
  etiqueta: string;
  // Por que se esta viendo este elemento (para un aviso: que paso y que
  // hacer); se muestra en la barra del recorrido.
  detalle?: string;
}

export interface Recorrido {
  // Migas que preceden al elemento actual ("Avisos", "Lotes / 0000258").
  migas: MigaPan[];
  volver: { etiqueta: string; ruta: string };
  // Nombre de cada elemento para "Aviso 3 de 12", "Cuenta 2 de 5".
  nombre: string;
  pasos: PasoRecorrido[];
  indice: number;
}

interface EstadoConRecorrido {
  recorrido: Recorrido;
}

export function leer_recorrido(estado: unknown): Recorrido | null {
  if (typeof estado !== "object" || estado === null || !("recorrido" in estado)) return null;
  const recorrido = (estado as EstadoConRecorrido).recorrido;
  const valido =
    Array.isArray(recorrido.pasos) &&
    recorrido.indice >= 0 &&
    recorrido.indice < recorrido.pasos.length;
  return valido ? recorrido : null;
}

export function ir_a_paso(navegar: NavigateFunction, recorrido: Recorrido, indice: number): void {
  const paso = recorrido.pasos[indice];
  if (!paso) return;
  void navegar(paso.ruta, { state: { recorrido: { ...recorrido, indice } } });
}

export function migas_con_recorrido(
  recorrido: Recorrido | null,
  por_defecto: MigaPan[],
  actual: string,
): MigaPan[] {
  return recorrido
    ? [...recorrido.migas, { etiqueta: actual }]
    : [...por_defecto, { etiqueta: actual }];
}
