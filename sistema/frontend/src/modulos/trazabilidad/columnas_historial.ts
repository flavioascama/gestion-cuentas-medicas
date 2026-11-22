import type { EventoHistorial } from "../../api/trazabilidad";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { nombre_actor, nombre_estado_evento, nombre_evento } from "./nombres_eventos";

// Columnas comunes del historial de la cuenta y del lote (RT-13).
export const COLUMNAS_HISTORIAL: ColumnaTabla<EventoHistorial>[] = [
  {
    clave: "ocurrido_en",
    encabezado: "Fecha y hora",
    formatear: (fila) => formatear_fecha_hora(fila.ocurrido_en),
  },
  {
    clave: "tipo_evento",
    encabezado: "Acción",
    formatear: (fila) => nombre_evento(fila.tipo_evento),
  },
  { clave: "actor", encabezado: "Actor", formatear: (fila) => nombre_actor(fila.actor) },
  {
    clave: "estado_previo",
    encabezado: "Estado previo",
    formatear: (fila) => nombre_estado_evento(fila.estado_previo),
  },
  {
    clave: "estado_nuevo",
    encabezado: "Estado nuevo",
    formatear: (fila) => nombre_estado_evento(fila.estado_nuevo),
  },
];
