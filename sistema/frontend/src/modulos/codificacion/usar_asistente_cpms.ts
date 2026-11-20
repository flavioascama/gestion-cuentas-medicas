import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  sugerir_codigo_cpms,
  type CandidatoCpms,
  type RespuestaSugerenciaCpms,
} from "../../api/cpms";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";

// Bajo este largo no se busca: evita una avalancha de resultados poco
// utiles con una o dos letras.
const _LARGO_MINIMO_BUSQUEDA = 3;

export function usar_asistente_cpms(cuenta_id: number, descripcion_inicial = "") {
  const [descripcion, set_descripcion] = useState(descripcion_inicial);
  const [candidato_elegido, set_candidato_elegido] = useState<CandidatoCpms | null>(null);
  const [mensaje_exito, set_mensaje_exito] = useState(false);

  const descripcion_diferida = usar_valor_diferido(descripcion.trim());
  const busqueda_habilitada = descripcion_diferida.length >= _LARGO_MINIMO_BUSQUEDA;

  const consulta_sugerencias = useQuery({
    queryKey: ["cpms", "sugerencias", descripcion_diferida, cuenta_id],
    queryFn: () =>
      sugerir_codigo_cpms(descripcion_diferida, { cuenta_medica_id: cuenta_id || undefined }),
    enabled: busqueda_habilitada,
  });

  const resultado: RespuestaSugerenciaCpms | null = busqueda_habilitada
    ? (consulta_sugerencias.data ?? null)
    : null;

  const cerrar_confirmacion_exitosa = () => {
    set_candidato_elegido(null);
    set_mensaje_exito(true);
    set_descripcion("");
  };

  return {
    descripcion,
    set_descripcion: (valor: string) => {
      set_mensaje_exito(false);
      set_descripcion(valor);
    },
    resultado,
    buscando: busqueda_habilitada && consulta_sugerencias.isFetching,
    error: busqueda_habilitada && consulta_sugerencias.isError ? consulta_sugerencias.error : null,
    candidato_elegido,
    set_candidato_elegido,
    mensaje_exito,
    cerrar_confirmacion_exitosa,
  };
}
