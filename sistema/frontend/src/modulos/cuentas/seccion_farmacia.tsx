import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { DetalleCuenta } from "../../api/cuentas";
import { quitar_producto } from "../../api/farmacia";
import { Boton } from "../../componentes_base/boton";
import { etiqueta_tipo_producto } from "../../componentes_base/mapa_tipos_producto";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { DialogoProductoFarmacia } from "./dialogo_producto_farmacia";
import { usar_en_correccion_validador } from "./usar_cuentas";
import estilos from "./detalle_cuenta.module.css";

type Producto = DetalleCuenta["productos"][number];

// RI-17: la farmacia se edita en los mismos estados en que se codifica la
// cuenta (antes de facturar, al corregir una rechazada, al refacturar, o si
// el validador observo su lote).
const _ESTADOS_EDITABLES = new Set(["REGISTRADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);

const _COLUMNAS: ColumnaTabla<Producto>[] = [
  { clave: "correlativo", encabezado: "N.°", alinear_centro: true },
  { clave: "nombre", encabezado: "Producto", formatear: (fila) => fila.nombre ?? "—" },
  { clave: "codigo_producto", encabezado: "Código" },
  {
    clave: "tipo_producto",
    encabezado: "Tipo",
    formatear: (fila) => etiqueta_tipo_producto(fila.tipo_producto),
  },
  { clave: "cantidad_venta", encabezado: "Cantidad", alinear_derecha: true },
  {
    clave: "fecha_dispensacion",
    encabezado: "Dispensado",
    formatear: (fila) => (fila.fecha_dispensacion ? formatear_fecha(fila.fecha_dispensacion) : "—"),
  },
  {
    clave: "monto_presentado",
    encabezado: "Monto",
    alinear_derecha: true,
    formatear: (fila) => formatear_monto(fila.monto_presentado),
  },
];

function columnas(al_quitar: ((id: number) => void) | null): ColumnaTabla<Producto>[] {
  if (!al_quitar) return _COLUMNAS;
  return [
    ..._COLUMNAS,
    {
      clave: "id",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_quitar(fila.id)}>
          Quitar
        </Boton>
      ),
    },
  ];
}

export function SeccionFarmacia({ cuenta }: { cuenta: DetalleCuenta }) {
  const { sesion } = usar_sesion();
  const cliente_consultas = useQueryClient();
  const [registrar, set_registrar] = useState(false);
  const en_correccion = usar_en_correccion_validador(cuenta.id);
  // Registran y quitan productos el analista y el auditor medico (2026-11-19).
  const registra = sesion?.roles.some((rol) => rol === "analista" || rol === "auditor") ?? false;
  const editable = registra && (_ESTADOS_EDITABLES.has(cuenta.estado) || en_correccion);
  const quitar = useMutation({
    mutationFn: (producto_id: number) => quitar_producto(cuenta.id, producto_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta.id] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Productos de farmacia</div>
      {editable ? (
        <div className={estilos.fila_accion}>
          <Boton variante="secundario" onClick={() => set_registrar(true)}>
            Registrar producto
          </Boton>
        </div>
      ) : null}
      <MensajeErrorMutacion
        error={quitar.error}
        texto_por_defecto="No se pudo quitar el producto."
      />
      <TablaDatos
        columnas={columnas(editable ? (id) => quitar.mutate(id) : null)}
        filas={cuenta.productos}
        obtener_clave={(fila) => fila.id}
        mensaje_vacio="La cuenta no tiene productos de farmacia."
      />
      {registrar ? (
        <DialogoProductoFarmacia
          cuenta_id={cuenta.id}
          fecha_prestacion={cuenta.fecha_prestacion}
          al_cerrar={() => set_registrar(false)}
        />
      ) : null}
    </div>
  );
}
