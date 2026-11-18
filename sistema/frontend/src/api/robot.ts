import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

// Navegacion visible del robot. El administrador activa la opcion, elige el
// modo y ve el registro (tarea, usuario y hora). El analista y el jefe ven
// en vivo el navegador del robot mientras hace la tarea que pidieron.
export type OpcionNavegacion = components["schemas"]["OpcionNavegacion"];
// La opcion mas si hay un robot encendido en un equipo con pantalla.
export type EstadoNavegacion = components["schemas"]["EstadoNavegacion"];
export type ModoNavegacion = OpcionNavegacion["modo"];
export type PasoRobot = components["schemas"]["PasoRobotRespuesta"];
export type ActividadRobot = components["schemas"]["ActividadRobotRespuesta"];
export type TrabajoEnVivo = components["schemas"]["TrabajoEnVivoRespuesta"];

export function consultar_navegacion_visible(): Promise<EstadoNavegacion> {
  return obtener<EstadoNavegacion>("/robot/navegacion-visible");
}

export function cambiar_navegacion_visible(opcion: OpcionNavegacion): Promise<EstadoNavegacion> {
  return enviar<EstadoNavegacion>("PUT", "/robot/navegacion-visible", opcion);
}

export function listar_actividad_robot(): Promise<ActividadRobot[]> {
  return obtener<ActividadRobot[]>("/robot/actividad");
}

export function listar_pasos_robot(trabajo_id: number): Promise<PasoRobot[]> {
  return obtener<PasoRobot[]>(`/robot/trabajos/${trabajo_id}/pasos`);
}

export function consultar_robot_en_vivo(): Promise<TrabajoEnVivo | null> {
  return obtener<TrabajoEnVivo | null>("/robot/en-vivo");
}

export function obtener_cuadro_en_vivo(trabajo_id: number, primera: boolean): Promise<Blob> {
  return obtener<Blob>(`/robot/en-vivo/${trabajo_id}/cuadro`, { primera });
}
