import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { solicitar_envio_susalud } from "../../api/lotes";
import {
  listar_control_susalud,
  registrar_declaracion_sin_facturacion,
  type ControlPeriodoSusalud,
} from "../../api/plazos";
import { obtener_trabajo } from "../../api/trabajos";
import { BotonConConfirmacion } from "../../componentes_base/dialogo_confirmar";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_periodo } from "../../utilidades/formato";
import { SesionPlataforma } from "../plataformas/sesion_plataforma";
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

// Declaracion jurada ya registrada: su fecha y, si fue tarde, fuera de plazo.
export function DeclaracionRegistrada({ fila }: { fila: ControlPeriodoSusalud }) {
  const fecha = formatear_fecha(fila.declarada_en ?? "");
  return fila.declarada_fuera_de_plazo ? (
    <Mensaje
      tipo="advertencia"
      texto={`Declaración jurada registrada el ${fecha}, fuera de plazo`}
    />
  ) : (
    <Mensaje tipo="exito" texto={`Declaración jurada registrada el ${fecha}`} />
  );
}

// Mes cerrado sin lotes que reportar: la declaracion jurada a SUSALUD.
export function DeclaracionSinFacturacion({ fila }: { fila: ControlPeriodoSusalud }) {
  const cliente_consultas = useQueryClient();
  const declaracion = useMutation({
    mutationFn: () => registrar_declaracion_sin_facturacion(fila.periodo),
    onSuccess: (respuesta) => {
      // La fila cambia en el acto; la consulta se vuelve a pedir igual.
      cliente_consultas.setQueryData<ControlPeriodoSusalud[]>(["plazos", "susalud"], (filas) =>
        filas?.map((f) =>
          f.periodo === respuesta.periodo ? { ...f, declarada_en: respuesta.registrada_en } : f,
        ),
      );
      void cliente_consultas.invalidateQueries({ queryKey: ["plazos", "susalud"] });
      void cliente_consultas.invalidateQueries({ queryKey: ["avisos"] });
    },
  });
  if (fila.declarada_en) return <DeclaracionRegistrada fila={fila} />;
  return (
    <>
      <BotonConConfirmacion
        variante="secundario"
        disabled={declaracion.isPending}
        titulo="Registrar declaración jurada"
        texto={`Se registrará que en ${formatear_periodo(fila.periodo)} no hubo lotes que reportar a SUSALUD. Esta acción no se puede deshacer.`}
        texto_confirmar="Registrar"
        al_confirmar={() => declaracion.mutate()}
      >
        Registrar declaración jurada
      </BotonConConfirmacion>
      <MensajeErrorMutacion
        error={declaracion.error}
        texto_por_defecto="No se pudo registrar la declaración jurada."
      />
    </>
  );
}

function BotonEnviarPeriodo(propiedades: {
  periodo: string;
  disabled: boolean;
  al_confirmar: () => void;
}) {
  const periodo = formatear_periodo(propiedades.periodo);
  return (
    <BotonConConfirmacion
      variante="secundario"
      disabled={propiedades.disabled}
      titulo="Enviar a SUSALUD"
      texto={`Se enviarán a SUSALUD los lotes de ${periodo}. Esta acción no se puede deshacer.`}
      texto_confirmar="Enviar"
      al_confirmar={propiedades.al_confirmar}
    >
      Enviar periodo {periodo} a SUSALUD
    </BotonConConfirmacion>
  );
}

export function EnvioPeriodoSusalud({ periodo, listos }: { periodo: string; listos: number }) {
  const cliente_consultas = useQueryClient();
  const [trabajo_id, set_trabajo_id] = useState<number | null>(null);
  const mutacion = useMutation({
    mutationFn: () => solicitar_envio_susalud(periodo),
    onSuccess: (respuesta) => set_trabajo_id(respuesta.trabajo_id),
  });
  // Mismo trabajo que muestra ProgresoTrabajo (misma clave de consulta): si
  // se agota, el boton vuelve a habilitarse.
  const trabajo = useQuery({
    queryKey: ["trabajo", trabajo_id],
    queryFn: () => obtener_trabajo(trabajo_id ?? 0),
    enabled: trabajo_id !== null,
  });
  const en_curso = trabajo_id !== null && trabajo.data?.estado !== "AGOTADO";
  // Estable entre renderizados: ProgresoTrabajo lo vuelve a llamar si cambia.
  const al_completar = useCallback(() => {
    void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] });
    void cliente_consultas.invalidateQueries({ queryKey: ["plazos", "susalud"] });
  }, [cliente_consultas]);

  return (
    <>
      {listos > 0 ? (
        <BotonEnviarPeriodo
          periodo={periodo}
          disabled={mutacion.isPending || en_curso}
          al_confirmar={() => mutacion.mutate()}
        />
      ) : null}
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
        texto_por_defecto="No se pudo iniciar el envío."
      />
      <SesionPlataforma
        plataforma="tedef_web"
        nombre="TEDEF Web"
        necesita={trabajo.data?.estado === "REQUIERE_SESION"}
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
        // El boton solo aparece si el periodo tiene lotes listos para enviar.
        <EnvioPeriodoSusalud periodo={periodo} listos={fila?.listos_envio ?? 0} />
      )}
    </div>
  );
}
