import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { solicitar_envio_susalud } from "../../api/lotes";
import { listar_control_susalud } from "../../api/plazos";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_periodo_legible } from "./filtros_lotes";
import estilos from "./bandeja_lotes.module.css";

// Lotes del periodo que el envio tomaria ahora: validados y aun sin enviar.
// Usa la misma consulta que la pestana "Reporte mensual a SUSALUD".
function usar_lotes_listos_susalud(periodo: string, habilitada: boolean): number {
  const control = useQuery({
    queryKey: ["plazos", "susalud"],
    queryFn: listar_control_susalud,
    enabled: habilitada,
  });
  const fila = control.data?.find((control_periodo) => control_periodo.periodo === periodo);
  return fila?.listos_envio ?? 0;
}

export function AccionEnvioSusalud({ periodo }: { periodo: string }) {
  const { sesion } = usar_sesion();
  const cliente_consultas = useQueryClient();
  const [trabajo_id, set_trabajo_id] = useState<number | null>(null);
  const visible = Boolean(sesion?.roles.includes("analista")) && Boolean(periodo);
  // El boton solo se habilita si el periodo tiene lotes listos para enviar.
  const listos = usar_lotes_listos_susalud(periodo, visible);

  const mutacion = useMutation({
    mutationFn: () => solicitar_envio_susalud(periodo),
    onSuccess: (respuesta) => set_trabajo_id(respuesta.trabajo_id),
  });
  // Estable entre renderizados: ProgresoTrabajo lo vuelve a llamar si cambia.
  const al_completar = useCallback(() => {
    void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] });
    void cliente_consultas.invalidateQueries({ queryKey: ["plazos", "susalud"] });
  }, [cliente_consultas]);

  if (!visible) return null;

  return (
    <div className={estilos.envio_susalud}>
      <Boton
        variante="secundario"
        onClick={() => mutacion.mutate()}
        disabled={listos === 0 || mutacion.isPending || trabajo_id !== null}
      >
        Enviar periodo {formatear_periodo_legible(periodo)} a SUSALUD
      </Boton>
      {trabajo_id !== null ? (
        <ProgresoTrabajo trabajo_id={trabajo_id} al_completar={al_completar} />
      ) : null}
      {mutacion.isSuccess && mutacion.data.trabajo_id === null ? (
        <Mensaje
          tipo="advertencia"
          texto="No hay lotes validados pendientes de envío en ese periodo."
        />
      ) : null}
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo encolar el envío."
      />
    </div>
  );
}
