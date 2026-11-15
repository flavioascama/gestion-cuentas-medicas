import type { EventoHistorial } from "../../api/trazabilidad";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";

// Columnas comunes del historial de la cuenta y del lote (RT-13).
export const COLUMNAS_HISTORIAL: ColumnaTabla<EventoHistorial>[] = [
  {
    clave: "ocurrido_en",
    encabezado: "Fecha y hora",
    formatear: (fila) => formatear_fecha_hora(fila.ocurrido_en),
  },
  { clave: "tipo_evento", encabezado: "Acción" },
  { clave: "actor", encabezado: "Actor" },
  {
    clave: "estado_previo",
    encabezado: "Estado previo",
    formatear: (fila) => fila.estado_previo ?? "—",
  },
  {
    clave: "estado_nuevo",
    encabezado: "Estado nuevo",
    formatear: (fila) => fila.estado_nuevo ?? "—",
  },
];
