import { useNavigate } from "react-router-dom";
import type { CuentaLote } from "../../api/lotes";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { IconoFlechaDerecha, IconoOjo } from "../../componentes_base/iconos_tabla";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import type { Recorrido } from "../../navegacion/recorrido";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { usar_cuentas_lote } from "./usar_lotes";
import estilos from "./detalle_lote.module.css";
import propios from "./seccion_cuentas_lote.module.css";

// Un lote es un conjunto de atenciones (cuentas): desde el lote se abre
// cada una y, ya en su detalle, se pasa a la siguiente del mismo lote o
// se vuelve al lote (rediseno del 2026-11-12, pedido del usuario: la
// tabla existia pero no se notaba que sus filas se podian abrir).

function asegurado(fila: CuentaLote): string {
  return `${fila.nombres_asegurado} ${fila.apellidos_asegurado}`;
}

function recorrido_del_lote(
  cuentas: CuentaLote[],
  indice: number,
  lote: { id: number; numero: string },
): Recorrido {
  return {
    migas: [
      { etiqueta: "Lotes", ruta: "/lotes" },
      { etiqueta: lote.numero, ruta: `/lotes/${lote.id}` },
    ],
    volver: { etiqueta: `Volver al lote ${lote.numero}`, ruta: `/lotes/${lote.id}` },
    nombre: "Cuenta",
    indice,
    pasos: cuentas.map((cuenta) => ({
      ruta: `/cuentas/${cuenta.id}`,
      etiqueta: cuenta.identificacion_interna,
      detalle: `${cuenta.identificacion_interna} · ${asegurado(cuenta)}${
        cuenta.fecha_prestacion ? ` · atención del ${formatear_fecha(cuenta.fecha_prestacion)}` : ""
      }`,
    })),
  };
}

function construir_columnas(al_ver: (fila: CuentaLote) => void): ColumnaTabla<CuentaLote>[] {
  return [
    {
      clave: "identificacion_interna",
      encabezado: "Cuenta",
      formatear: (fila) => (
        <span className={propios.enlace_cuenta}>
          {fila.identificacion_interna}
          <IconoFlechaDerecha />
        </span>
      ),
    },
    { clave: "nombres_asegurado", encabezado: "Asegurado", formatear: asegurado },
    {
      clave: "fecha_prestacion",
      encabezado: "Atención",
      formatear: (fila) => (fila.fecha_prestacion ? formatear_fecha(fila.fecha_prestacion) : "—"),
    },
    {
      clave: "estado",
      encabezado: "Estado",
      formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
    },
    {
      clave: "monto",
      encabezado: "Monto",
      alinear_derecha: true,
      formatear: (fila) => formatear_monto(fila.monto),
    },
    {
      clave: "id",
      encabezado: "Acciones",
      alinear_centro: true,
      formatear: (fila) => (
        <button
          type="button"
          className={propios.boton_ver}
          aria-label={`Ver la cuenta ${fila.identificacion_interna}`}
          title="Ver detalle"
          onClick={(evento) => {
            evento.stopPropagation();
            al_ver(fila);
          }}
        >
          <IconoOjo />
        </button>
      ),
    },
  ];
}

export function SeccionCuentasLote({ lote_id, numero }: { lote_id: number; numero: string }) {
  const navegar = useNavigate();
  const consulta = usar_cuentas_lote(lote_id);
  const cuentas = consulta.data ?? [];
  const abrir = (fila: CuentaLote) => {
    const indice = cuentas.findIndex((cuenta) => cuenta.id === fila.id);
    void navegar(`/cuentas/${fila.id}`, {
      state: { recorrido: recorrido_del_lote(cuentas, indice, { id: lote_id, numero }) },
    });
  };

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>
        Cuentas incluidas en el lote{cuentas.length > 0 ? ` (${cuentas.length})` : ""}
      </div>
      <TablaDatos
        columnas={construir_columnas(abrir)}
        filas={cuentas}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay cuentas en este lote."
        al_hacer_clic_fila={abrir}
      />
    </div>
  );
}
