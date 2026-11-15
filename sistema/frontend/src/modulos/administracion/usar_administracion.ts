import { useQuery } from "@tanstack/react-query";
import { listar_versiones_cpms } from "../../api/cpms";

export function usar_versiones_cpms() {
  return useQuery({ queryKey: ["administracion", "cpms"], queryFn: listar_versiones_cpms });
}
