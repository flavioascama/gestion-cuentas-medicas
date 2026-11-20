import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  consultar_copago_asegurado,
  consultar_copago_cobrado,
  type CopagoCobrado,
} from "../../api/copago";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { BotonRegistrarCobro } from "./dialogo_cobro_copago";

export interface FilaMonto {
  etiqueta: string;
  valor: ReactNode;
}

const _TERMINALES = new Set(["CERRADA", "ANULADA"]);

function valor_cobrado(copago: CopagoCobrado): string {
  return `${formatear_monto(copago.monto)} · ${formatear_fecha(copago.fecha)} · ${copago.referencia}`;
}

// El copago que el calculo de montos atribuye al asegurado y el que la
// clinica ya le cobro (2026-11-19).
export function usar_filas_copago(cuenta_id: number, estado: string): FilaMonto[] {
  const { sesion } = usar_sesion();
  const asegurado = useQuery({
    queryKey: ["cuentas", cuenta_id, "copago-asegurado"],
    queryFn: () => consultar_copago_asegurado(cuenta_id),
  });
  const cobrado = useQuery({
    queryKey: ["cuentas", cuenta_id, "copago-cobrado"],
    queryFn: () => consultar_copago_cobrado(cuenta_id),
  });
  const monto_asegurado = asegurado.data?.monto;
  const registra = Boolean(sesion?.roles.includes("analista")) && !_TERMINALES.has(estado);
  let valor_cobro: ReactNode = "—";
  if (cobrado.data) valor_cobro = valor_cobrado(cobrado.data);
  else if (registra && cobrado.data === null) {
    valor_cobro = <BotonRegistrarCobro cuenta_id={cuenta_id} />;
  }
  return [
    {
      etiqueta: "Copago del asegurado",
      valor: monto_asegurado != null ? formatear_monto(monto_asegurado) : "—",
    },
    { etiqueta: "Copago cobrado", valor: valor_cobro },
  ];
}
