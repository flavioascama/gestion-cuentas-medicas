import type { ProcedimientoPorCodificar } from "../../api/atenciones";
import { Boton } from "../../componentes_base/boton";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { etiqueta_area_procedimiento } from "./etiquetas_atencion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";

function construir_columnas(
  al_codificar: ((pendiente: ProcedimientoPorCodificar) => void) | null,
): ColumnaTabla<ProcedimientoPorCodificar>[] {
  const columnas: ColumnaTabla<ProcedimientoPorCodificar>[] = [
    { clave: "descripcion", encabezado: "Descripción" },
    {
      clave: "area",
      encabezado: "Área",
      formatear: (fila) => etiqueta_area_procedimiento(fila.area),
    },
    { clave: "cantidad", encabezado: "Cantidad", alinear_derecha: true },
    {
      clave: "monto_unitario",
      encabezado: "Monto unitario",
      alinear_derecha: true,
      formatear: (fila) => formatear_monto(fila.monto_unitario),
    },
    {
      clave: "fecha",
      encabezado: "Fecha",
      formatear: (fila) => formatear_fecha(fila.fecha),
    },
  ];
  if (!al_codificar) return columnas;
  return [
    ...columnas,
    {
      clave: "id",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_codificar(fila)}>
          Codificar
        </Boton>
      ),
    },
  ];
}

export function ListaPorCodificar({
  pendientes,
  al_codificar,
}: {
  pendientes: ProcedimientoPorCodificar[];
  al_codificar: ((pendiente: ProcedimientoPorCodificar) => void) | null;
}) {
  return (
    <TablaDatos
      columnas={construir_columnas(al_codificar)}
      filas={pendientes}
      obtener_clave={(fila) => fila.id}
    />
  );
}
