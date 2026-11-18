import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { remitir_lote, solicitar_carga_en_validador } from "../../api/lotes";
import { obtener_trabajo } from "../../api/trabajos";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { SesionPlataforma } from "../plataformas/sesion_plataforma";

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

  function al_completar_carga(): void {
    void cliente_consultas.invalidateQueries({ queryKey: ["lotes", lote_id] });
  }

  return { cargar_validador, remitir_iafas, trabajo_id, al_completar_carga };
}

export type AccionesLote = ReturnType<typeof usar_acciones_lote>;

// Tabla 46: validar el lote (cargarlo en el validador) es del analista y del
// jefe; remitirlo a la IAFAS, solo del analista.
function puede_operar(roles: readonly string[] | undefined, estado: string): boolean {
  if (estado === "GENERADO") return Boolean(roles?.includes("analista") || roles?.includes("jefe"));
  return Boolean(roles?.includes("analista"));
}

export function BotonAccionLote({ estado, acciones }: { estado: string; acciones: AccionesLote }) {
  const { sesion } = usar_sesion();
  if (!puede_operar(sesion?.roles, estado)) return null;

  if (estado === "GENERADO") {
    return (
      <Boton
        variante="primario"
        onClick={() => acciones.cargar_validador.mutate()}
        disabled={acciones.cargar_validador.isPending || acciones.trabajo_id !== null}
      >
        Cargar en el validador
      </Boton>
    );
  }
  if (estado === "VALIDADO") {
    return (
      <Boton
        variante="primario"
        onClick={() => acciones.remitir_iafas.mutate()}
        disabled={acciones.remitir_iafas.isPending}
      >
        Remitir a la IAFAS
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
        texto_por_defecto="No se pudo encolar la carga."
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

export function ContenidoAccionLote({
  estado,
  acciones,
}: {
  estado: string;
  acciones: AccionesLote;
}) {
  const { sesion } = usar_sesion();
  if (!puede_operar(sesion?.roles, estado)) return null;

  if (estado === "GENERADO") return <ContenidoCargaValidador acciones={acciones} />;
  if (estado === "VALIDADO") {
    return (
      <MensajeErrorMutacion
        error={acciones.remitir_iafas.error}
        texto_por_defecto="No se pudo remitir el lote."
      />
    );
  }
  return null;
}
