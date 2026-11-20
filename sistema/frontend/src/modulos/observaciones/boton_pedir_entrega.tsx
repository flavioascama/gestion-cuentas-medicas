import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pedir_nueva_entrega, type Observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

// Vuelve a pedir la entrega de la respuesta a la IAFAS (2026-11-19).
export function BotonPedirEntrega({ observacion }: { observacion: Observacion }) {
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: () => pedir_nueva_entrega(observacion.id),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({
        queryKey: ["cuentas", observacion.cuenta_medica_id, "observaciones"],
      });
    },
  });
  return (
    <>
      <Boton variante="terciario" onClick={() => mutacion.mutate()} disabled={mutacion.isPending}>
        Pedir entrega
      </Boton>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo pedir." />
    </>
  );
}
