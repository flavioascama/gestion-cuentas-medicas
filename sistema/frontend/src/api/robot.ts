import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

// Navegacion visible del robot: el administrador activa la opcion; el
// analista y el jefe ven la captura de cada paso del robot.
export type OpcionNavegacion = components["schemas"]["OpcionNavegacion"];
export type PasoRobot = components["schemas"]["PasoRobotRespuesta"];
export type ActividadRobot = components["schemas"]["ActividadRobotRespuesta"];

export function consultar_navegacion_visible(): Promise<OpcionNavegacion> {
  return obtener<OpcionNavegacion>("/robot/navegacion-visible");
}

export function cambiar_navegacion_visible(activa: boolean): Promise<OpcionNavegacion> {
  return enviar<OpcionNavegacion>("PUT", "/robot/navegacion-visible", { activa });
}

export function listar_actividad_robot(): Promise<ActividadRobot[]> {
  return obtener<ActividadRobot[]>("/robot/actividad");
}

export function listar_pasos_robot(trabajo_id: number): Promise<PasoRobot[]> {
  return obtener<PasoRobot[]>(`/robot/trabajos/${trabajo_id}/pasos`);
}

export function obtener_captura_paso(trabajo_id: number, orden: number): Promise<Blob> {
  return obtener<Blob>(`/robot/trabajos/${trabajo_id}/pasos/${orden}/captura`);
}
