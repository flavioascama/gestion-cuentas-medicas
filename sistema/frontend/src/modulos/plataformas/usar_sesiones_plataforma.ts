import { useQuery } from "@tanstack/react-query";
import { listar_sesiones_plataforma } from "../../api/plataformas";

const _ESTADOS_EN_CURSO = new Set(["SOLICITADA", "ESPERANDO_CAPTCHA", "CAPTCHA_RESPONDIDO"]);

export function usar_sesion_vigente_plataforma(plataforma: string) {
  const consulta = useQuery({
    queryKey: ["plataformas", "sesiones", plataforma],
    queryFn: () => listar_sesiones_plataforma(plataforma),
    refetchInterval: (query) => {
      const sesiones = query.state.data ?? [];
      const mas_reciente = sesiones[0];
      return mas_reciente && _ESTADOS_EN_CURSO.has(mas_reciente.estado) ? 2000 : 8000;
    },
  });

  const mas_reciente = consulta.data?.[0];
  return { consulta, sesion_vigente: mas_reciente };
}
