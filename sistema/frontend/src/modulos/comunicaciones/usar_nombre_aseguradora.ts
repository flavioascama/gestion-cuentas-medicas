import { useQuery } from "@tanstack/react-query";
import { listar_iafas } from "../../api/iafas";

// El nombre de la aseguradora por su codigo; mientras carga, el codigo.
export function usar_nombre_aseguradora(): (codigo: string) => string {
  const consulta = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  return (codigo) =>
    consulta.data?.find((iafas) => iafas.codigo === codigo)?.razon_social ?? codigo;
}
