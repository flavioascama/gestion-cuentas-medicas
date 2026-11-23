import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  remitir_lote,
  solicitar_carga_en_validador,
  solicitar_monitoreo_respuesta,
} from "../../api/lotes";
import { obtener_trabajo } from "../../api/trabajos";
import { Boton } from "../../componentes_base/boton";
import { BotonConConfirmacion } from "../../componentes_base/dialogo_confirmar";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { SesionPlataforma } from "../plataformas/sesion_plataforma";
import { consulta_en_curso } from "./usar_lotes";

// Las mutaciones viven en un solo hook (no uno por boton) porque el
// boton -- ahora en la cabecera, junto al titulo -- y su contenido
// secundario (progreso, mensaje de error, el codigo de verificacion de
// TEDEF Web) -- debajo del stepper, lejos en el arbol -- necesitan ver el
// mismo estado de mutacion; declarar un useMutation en cada uno los
// desincronizaria.
export function usar_acciones_lote(lote_id: number) {
  const cliente_consultas = useQueryClient();
  const [trabajo_id, set_trabajo_id] = useState<number | null>(null);

  const cargar_validador = useMutation({
    mutationFn: () => solicitar_carga_en_validador(lote_id),
    onSuccess: (respuesta) => set_trabajo_id(respuesta.trabajo_id),
  });

  const remitir_iafas = useMutation({
    mutationFn: () => remitir_lote(lote_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["lotes", lote_id] }),
  });

  // El avance se lee del propio lote (proxima_consulta), que se refresca solo.
  const consultar_respuesta = useMutation({
    mutationFn: () => solicitar_monitoreo_respuesta(lote_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["lotes", lote_id] }),
  });

  // Igual con la carga en el validador.
  const trabajo_carga = useQuery({
    queryKey: ["trabajo", trabajo_id],
    queryFn: () => obtener_trabajo(trabajo_id ?? 0),
    enabled: trabajo_id !== null,
  });
  const carga_en_curso = trabajo_id !== null && trabajo_carga.data?.estado !== "AGOTADO";

  function al_completar_carga(): void {
    void cliente_consultas.invalidateQueries({ queryKey: ["lotes", lote_id] });
  }

  return {
    cargar_validador,
    remitir_iafas,
    consultar_respuesta,
    trabajo_id,
    carga_en_curso,
    al_completar_carga,
  };
}

export type AccionesLote = ReturnType<typeof usar_acciones_lote>;

// Tabla 46: validar el lote (cargarlo en el validador, o volver a pedir la
// validacion de uno ya cargado) es del analista y del jefe; remitirlo a la
// IAFAS, solo del analista.
const _ESTADOS_VALIDACION = ["GENERADO", "CARGADO_VALIDADOR"];

function puede_operar(roles: readonly string[] | undefined, estado: string): boolean {
  if (_ESTADOS_VALIDACION.includes(estado)) {
    return Boolean(roles?.includes("analista") || roles?.includes("jefe"));
  }
  return Boolean(roles?.includes("analista"));
}

type LoteAccion = {
  estado: string;
  proxima_consulta?: string | null;
  validacion_reintentable: boolean;
  vigente: boolean;
};

// Un lote ya cargado se vuelve a validar solo si su trabajo anterior termino.
function pide_validacion(lote: LoteAccion): boolean {
  return (
    lote.estado === "GENERADO" ||
    (lote.estado === "CARGADO_VALIDADOR" && lote.validacion_reintentable)
  );
}

export function BotonAccionLote({ lote, acciones }: { lote: LoteAccion; acciones: AccionesLote }) {
  const { estado } = lote;
  const { sesion } = usar_sesion();
  if (!puede_operar(sesion?.roles, estado) || !lote.vigente) return null;

  if (pide_validacion(lote)) {
    return (
      <Boton
        variante="primario"
        onClick={() => acciones.cargar_validador.mutate()}
        disabled={acciones.cargar_validador.isPending || acciones.carga_en_curso}
      >
        Cargar en el validador
      </Boton>
    );
  }
  if (estado === "VALIDADO") {
    return (
      <BotonConConfirmacion
        variante="primario"
        disabled={acciones.remitir_iafas.isPending}
        titulo="Remitir a la IAFAS"
        texto="Se remitirá el lote a la IAFAS. Esta acción no se puede deshacer."
        texto_confirmar="Remitir"
        al_confirmar={() => acciones.remitir_iafas.mutate()}
      >
        Remitir a la IAFAS
      </BotonConConfirmacion>
    );
  }
  if (estado === "REMITIDO_IAFAS") {
    return (
      <Boton
        variante="primario"
        onClick={() => acciones.consultar_respuesta.mutate()}
        disabled={
          acciones.consultar_respuesta.isPending || consulta_en_curso(lote.proxima_consulta)
        }
      >
        Consultar respuesta de la IAFAS
      </Boton>
    );
  }
  return null;
}

function ContenidoCargaValidador({ acciones }: { acciones: AccionesLote }) {
  // El mismo trabajo que muestra ProgresoTrabajo (misma clave de consulta).
  const trabajo = useQuery({
    queryKey: ["trabajo", acciones.trabajo_id],
    queryFn: () => obtener_trabajo(acciones.trabajo_id ?? 0),
    enabled: acciones.trabajo_id !== null,
  });
  return (
    <div>
      {acciones.trabajo_id !== null ? (
        <ProgresoTrabajo
          trabajo_id={acciones.trabajo_id}
          texto_en_curso="Cargando en el validador"
          al_completar={acciones.al_completar_carga}
        />
      ) : null}
      <MensajeErrorMutacion
        error={acciones.cargar_validador.error}
        texto_por_defecto="No se pudo iniciar la carga."
      />
      {/* La sesion con TEDEF Web se maneja sola (2026-11-18): se pide cuando
          la carga la necesita y la persona solo responde el codigo. */}
      <SesionPlataforma
        plataforma="tedef_web"
        nombre="TEDEF Web"
        necesita={trabajo.data?.estado === "REQUIERE_SESION"}
      />
    </div>
  );
}

// Lo que pasa con la respuesta de la IAFAS a un lote remitido.
function texto_espera(proxima_consulta: string | null | undefined): string | null {
  if (proxima_consulta == null) return null;
  if (consulta_en_curso(proxima_consulta)) return "Consultando la respuesta de la IAFAS…";
  return `Esperando la respuesta de la IAFAS. Próxima consulta: ${formatear_fecha_hora(proxima_consulta)}.`;
}

export function ContenidoAccionLote({
  lote,
  acciones,
}: {
  lote: LoteAccion;
  acciones: AccionesLote;
}) {
  const { estado, vigente, proxima_consulta } = lote;
  const { sesion } = usar_sesion();
  if (!puede_operar(sesion?.roles, estado) || !vigente) return null;

  if (_ESTADOS_VALIDACION.includes(estado)) return <ContenidoCargaValidador acciones={acciones} />;
  if (estado === "VALIDADO") {
    return (
      <MensajeErrorMutacion
        error={acciones.remitir_iafas.error}
        texto_por_defecto="No se pudo remitir el lote."
      />
    );
  }
  if (estado === "REMITIDO_IAFAS") {
    return (
      <div>
        <span>{texto_espera(proxima_consulta)}</span>
        <MensajeErrorMutacion
          error={acciones.consultar_respuesta.error}
          texto_por_defecto="No se pudo consultar la respuesta de la IAFAS."
        />
      </div>
    );
  }
  return null;
}
