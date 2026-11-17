import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listar_lotes_sugeridos, type LoteSugerido } from "../../api/lotes";

export function clave_lote_sugerido(sugerido: LoteSugerido): string {
  return `${sugerido.iafas_id}_${sugerido.periodo}`;
}

// El sistema ya agrupa las cuentas facturadas por IAFAS y periodo (el mes
// del comprobante): el analista elige un grupo y, si hace falta, desmarca
// las cuentas que no deben entrar.
export function usar_formulario_generar_lote() {
  const consulta = useQuery({ queryKey: ["lotes", "sugeridos"], queryFn: listar_lotes_sugeridos });
  const [clave_elegida, set_clave_elegida] = useState<string | null>(null);
  const [excluidas, set_excluidas] = useState<number[]>([]);

  const sugeridos = consulta.data ?? [];
  // Con un solo grupo no hay nada que elegir: queda seleccionado.
  const unico = sugeridos.length === 1 ? sugeridos[0] : undefined;
  const elegido = sugeridos.find((s) => clave_lote_sugerido(s) === clave_elegida) ?? unico;
  const cuentas = elegido?.cuentas ?? [];
  const cuenta_ids = cuentas.map((c) => c.cuenta_id).filter((id) => !excluidas.includes(id));

  const elegir = (clave: string) => {
    set_clave_elegida(clave);
    set_excluidas([]);
  };

  const alternar_cuenta = (cuenta_id: number) => {
    set_excluidas((actual) =>
      actual.includes(cuenta_id) ? actual.filter((id) => id !== cuenta_id) : [...actual, cuenta_id],
    );
  };

  const alternar_todas = () => {
    set_excluidas(excluidas.length === 0 ? cuentas.map((c) => c.cuenta_id) : []);
  };

  return {
    consulta,
    sugeridos,
    elegido,
    cuenta_ids,
    excluidas,
    elegir,
    alternar_cuenta,
    alternar_todas,
  };
}
