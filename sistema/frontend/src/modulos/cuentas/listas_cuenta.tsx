import { useState } from "react";
import { quitar_procedimiento } from "../../api/cpms";
import type { DetalleCuenta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { usar_puede_codificar } from "./codificacion_cuenta";
import { DialogoConfirmarQuitar } from "./dialogo_confirmar_quitar";
import estilos from "./detalle_cuenta.module.css";

type Procedimiento = DetalleCuenta["procedimientos"][number];

function importe(procedimiento: Procedimiento): number {
  return procedimiento.cantidad * Number(procedimiento.monto_unitario);
}

// Con su precio (2026-11-18): lo que el auditor registro al codificar es lo
// que despues se factura, y antes no se veia en ninguna parte de la cuenta.
const _COLUMNAS_PROCEDIMIENTOS: ColumnaTabla<Procedimiento>[] = [
  {
    clave: "fecha",
    encabezado: "Fecha",
    formatear: (fila) => (fila.fecha ? formatear_fecha(fila.fecha) : "—"),
  },
  { clave: "codigo_asignado", encabezado: "Código CPMS" },
  { clave: "descripcion_registrada", encabezado: "Descripción registrada" },
  { clave: "cantidad", encabezado: "Cantidad", alinear_derecha: true },
  {
    clave: "monto_unitario",
    encabezado: "Precio unitario",
    alinear_derecha: true,
    formatear: (fila) => formatear_monto(fila.monto_unitario),
  },
  {
    clave: "id",
    encabezado: "Importe",
    alinear_derecha: true,
    formatear: (fila) => formatear_monto(importe(fila)),
  },
];

// Mismo "Quitar" que la farmacia: solo para quien puede codificar la cuenta.
function columnas_procedimientos(
  al_quitar: ((fila: Procedimiento) => void) | null,
): ColumnaTabla<Procedimiento>[] {
  if (!al_quitar) return _COLUMNAS_PROCEDIMIENTOS;
  return [
    ..._COLUMNAS_PROCEDIMIENTOS,
    {
      clave: "id",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_quitar(fila)}>
          Quitar
        </Boton>
      ),
    },
  ];
}

// Pestania "Procedimientos". El auditor medico agrega aqui cada procedimiento
// con el asistente de codificacion CPMS (2026-11-18: el boton vivia solo en
// la cabecera de la cuenta).
export function SeccionProcedimientos({
  cuenta,
  al_codificar,
}: {
  cuenta: DetalleCuenta;
  al_codificar: () => void;
}) {
  const puede_codificar = usar_puede_codificar(cuenta.estado, cuenta.id);
  const [por_quitar, set_por_quitar] = useState<Procedimiento | null>(null);
  const total = cuenta.procedimientos.reduce((suma, fila) => suma + importe(fila), 0);
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Procedimientos</div>
      {puede_codificar ? (
        <div className={estilos.fila_accion}>
          <Boton variante="primario" onClick={al_codificar}>
            Agregar procedimiento
          </Boton>
        </div>
      ) : null}
      <TablaDatos
        columnas={columnas_procedimientos(puede_codificar ? set_por_quitar : null)}
        filas={cuenta.procedimientos}
        obtener_clave={(fila) => fila.id}
        mensaje_vacio="La cuenta no tiene procedimientos confirmados."
      />
      {cuenta.procedimientos.length > 0 ? (
        <div className={estilos.total_tabla}>
          <span>Total de procedimientos</span>
          <span>{formatear_monto(total)}</span>
        </div>
      ) : null}
      {por_quitar ? (
        <DialogoConfirmarQuitar
          titulo="Quitar procedimiento"
          cuenta_id={cuenta.id}
          texto={`¿Quitar el procedimiento ${por_quitar.codigo_asignado} de la cuenta?`}
          texto_error="No se pudo quitar el procedimiento."
          quitar={() => quitar_procedimiento(cuenta.id, por_quitar.id)}
          al_cerrar={() => set_por_quitar(null)}
        />
      ) : null}
    </div>
  );
}
