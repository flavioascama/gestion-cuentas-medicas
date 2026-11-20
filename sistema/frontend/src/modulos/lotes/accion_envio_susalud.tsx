import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { solicitar_envio_susalud } from "../../api/lotes";
import {
  listar_control_susalud,
  registrar_declaracion_sin_facturacion,
  type ControlPeriodoSusalud,
} from "../../api/plazos";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha } from "../../utilidades/formato";
import { formatear_periodo_legible } from "./filtros_lotes";
import estilos from "./bandeja_lotes.module.css";

// Control del periodo: lotes que el envio tomaria ahora (validados y aun sin
// enviar) y, en un mes sin lotes, su declaracion jurada. Usa la misma
// consulta que la pestana "Reporte mensual a SUSALUD".
function usar_control_periodo_susalud(
  periodo: string,
  habilitada: boolean,
): ControlPeriodoSusalud | undefined {
  const control = useQuery({
    queryKey: ["plazos", "susalud"],
    queryFn: listar_control_susalud,
    enabled: habilitada,
  });
  return control.data?.find((control_periodo) => control_periodo.periodo === periodo);
}

// Mes cerrado sin lotes que reportar: la declaracion jurada a SUSALUD.
function DeclaracionSinFacturacion({ fila }: { fila: ControlPeriodoSusalud }) {
  const cliente_consultas = useQueryClient();
  const declaracion = useMutation({
    mutationFn: () => registrar_declaracion_sin_facturacion(fila.periodo),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["plazos", "susalud"] });
      void cliente_consultas.invalidateQueries({ queryKey: ["avisos"] });
    },
  });
  if (fila.declarada_en) {
    return (
      <Mensaje
        tipo="exito"
        texto={`Declaración jurada registrada el ${formatear_fecha(fila.declarada_en)}`}
      />
    );
  }
  return (
    <>
      <Boton
        variante="secundario"
        onClick={() => declaracion.mutate()}
        disabled={declaracion.isPending}
      >
        Registrar declaración jurada
      </Boton>
      <MensajeErrorMutacion
        error={declaracion.error}
        texto_por_defecto="No se pudo registrar la declaración jurada."
      />
    </>
  );
}

function EnvioPeriodoSusalud({ periodo, listos }: { periodo: string; listos: number }) {
  const cliente_consultas = useQueryClient();
  const [trabajo_id, set_trabajo_id] = useState<number | null>(null);
  const mutacion = useMutation({
    mutationFn: () => solicitar_envio_susalud(periodo),
    onSuccess: (respuesta) => set_trabajo_id(respuesta.trabajo_id),
  });
  // Estable entre renderizados: ProgresoTrabajo lo vuelve a llamar si cambia.
  const al_completar = useCallback(() => {
    void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] });
    void cliente_consultas.invalidateQueries({ queryKey: ["plazos", "susalud"] });
  }, [cliente_consultas]);

  return (
    <>
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
          texto="No hay lotes remitidos pendientes de envío en ese periodo."
        />
      ) : null}
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo encolar el envío."
      />
    </>
  );
}

export function AccionEnvioSusalud({ periodo }: { periodo: string }) {
  const { sesion } = usar_sesion();
  const visible = Boolean(sesion?.roles.includes("analista")) && Boolean(periodo);
  const fila = usar_control_periodo_susalud(periodo, visible);

  if (!visible) return null;

  return (
    <div className={estilos.envio_susalud}>
      {fila !== undefined && fila.lotes === 0 ? (
        <DeclaracionSinFacturacion fila={fila} />
      ) : (
        // El boton solo se habilita si el periodo tiene lotes listos para enviar.
        <EnvioPeriodoSusalud periodo={periodo} listos={fila?.listos_envio ?? 0} />
      )}
    </div>
  );
}
