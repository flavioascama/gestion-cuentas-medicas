import type { DetalleCuenta } from "../../api/cuentas";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import estilos from "./detalle_cuenta.module.css";

type Procedimiento = DetalleCuenta["procedimientos"][number];

const _COLUMNAS_PROCEDIMIENTOS: ColumnaTabla<Procedimiento>[] = [
  { clave: "codigo_asignado", encabezado: "Código CPMS" },
  { clave: "descripcion_registrada", encabezado: "Descripción registrada" },
  { clave: "cantidad", encabezado: "Cantidad", alinear_derecha: true },
];

// Se dividio en dos componentes exportados (antes un unico ListasCuenta
// que renderizaba ambas secciones seguidas) para que el rediseno
// "resumen + pestanias" del detalle de cuenta pueda darle una pestania
// propia a cada tabla, en vez de mostrarlas siempre juntas.

export function SeccionProcedimientos({ cuenta }: { cuenta: DetalleCuenta }) {
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Procedimientos</div>
      <TablaDatos
        columnas={_COLUMNAS_PROCEDIMIENTOS}
        filas={cuenta.procedimientos}
        obtener_clave={(fila) => fila.codigo_asignado}
        mensaje_vacio="La cuenta no tiene procedimientos confirmados."
      />
    </div>
  );
}
