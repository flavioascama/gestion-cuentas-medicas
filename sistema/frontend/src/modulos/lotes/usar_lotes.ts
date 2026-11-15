import { useQuery } from "@tanstack/react-query";
import {
  obtener_acuses_lote,
  obtener_cuentas_lote,
  obtener_lote,
  obtener_prevalidacion_lote,
  obtener_validacion_oficial_lote,
  listar_lotes,
  type FiltrosListarLotes,
} from "../../api/lotes";

export function usar_bandeja_lotes(filtros: FiltrosListarLotes) {
  return useQuery({
    queryKey: ["lotes", filtros],
    queryFn: () => listar_lotes(filtros),
  });
}

export function usar_detalle_lote(lote_id: number) {
  return useQuery({
    queryKey: ["lotes", lote_id],
    queryFn: () => obtener_lote(lote_id),
  });
}

export function usar_prevalidacion_lote(lote_id: number) {
  return useQuery({
    queryKey: ["lotes", lote_id, "prevalidacion"],
    queryFn: () => obtener_prevalidacion_lote(lote_id),
    retry: false,
  });
}

export function usar_validacion_oficial_lote(lote_id: number) {
  return useQuery({
    queryKey: ["lotes", lote_id, "validacion-oficial"],
    queryFn: () => obtener_validacion_oficial_lote(lote_id),
  });
}

export function usar_acuses_lote(lote_id: number) {
  return useQuery({
    queryKey: ["lotes", lote_id, "acuses"],
    queryFn: () => obtener_acuses_lote(lote_id),
  });
}

export function usar_cuentas_lote(lote_id: number) {
  return useQuery({
    queryKey: ["lotes", lote_id, "cuentas"],
    queryFn: () => obtener_cuentas_lote(lote_id),
  });
}
