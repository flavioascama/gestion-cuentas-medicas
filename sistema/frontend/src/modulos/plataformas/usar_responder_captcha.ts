import { useMutation, useQueryClient } from "@tanstack/react-query";
import { responder_captcha } from "../../api/plataformas";

export function usar_responder_captcha(
  sesion_id: number,
  plataforma: string,
  al_exito: () => void,
  al_error: () => void,
) {
  const cliente_consultas = useQueryClient();

  return useMutation({
    mutationFn: (respuesta: string) => responder_captcha(sesion_id, respuesta),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({
        queryKey: ["plataformas", "sesiones", plataforma],
      });
      al_exito();
    },
    onError: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["plataformas", "captcha", sesion_id] });
      al_error();
    },
  });
}
