import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { listar_cuentas } from "../../api/cuentas";
import { listar_iafas } from "../../api/iafas";

export function usar_formulario_generar_lote() {
  const [iafas_id, set_iafas_id] = useState("");
  const [periodo, set_periodo] = useState("");
  const [cuenta_ids, set_cuenta_ids] = useState<number[]>([]);

  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  const iafas_elegida = consulta_iafas.data?.find((i) => String(i.id) === iafas_id);

  const consulta_cuentas = useQuery({
    queryKey: ["cuentas", "facturadas", iafas_elegida?.codigo],
    queryFn: () => listar_cuentas("FACTURADA"),
    enabled: Boolean(iafas_elegida),
  });

  const cuentas_elegibles = useMemo(
    () =>
      (consulta_cuentas.data ?? []).filter(
        (cuenta) => cuenta.iafas_codigo === iafas_elegida?.codigo,
      ),
    [consulta_cuentas.data, iafas_elegida],
  );

  const elegir_iafas = (valor: string) => {
    set_iafas_id(valor);
    set_cuenta_ids([]);
  };

  const alternar_cuenta = (cuenta_id: number) => {
    set_cuenta_ids((actual) =>
      actual.includes(cuenta_id) ? actual.filter((id) => id !== cuenta_id) : [...actual, cuenta_id],
    );
  };

  return {
    iafas_id,
    periodo,
    cuenta_ids,
    consulta_iafas,
    iafas_elegida,
    cuentas_elegibles,
    set_periodo,
    elegir_iafas,
    alternar_cuenta,
  };
}
