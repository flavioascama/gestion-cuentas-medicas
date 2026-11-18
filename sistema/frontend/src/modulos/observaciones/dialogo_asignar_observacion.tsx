import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  asignar_responsable_observacion,
  listar_responsables_posibles,
  type Observacion,
} from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";

type Naturaleza = "ADMINISTRATIVA" | "TECNICA" | "FINANCIERA";

// Tabla 60: quien responde cada naturaleza de observacion.
const _ROL_QUE_RESPONDE: Record<string, string> = {
  ADMINISTRATIVA: "analista",
  TECNICA: "auditor",
  FINANCIERA: "analista",
};

interface Propiedades {
  cuenta_id: number;
  observacion: Observacion;
  al_cerrar: () => void;
  al_asignar: () => void;
}

// El responsable se elige de la lista de personas que pueden responder esa
// naturaleza (2026-11-18): antes se escribia el numero interno del usuario.
function CamposAsignarObservacion({
  naturaleza,
  responsable,
  al_elegir_responsable,
  naturaleza_corregida,
  al_corregir_naturaleza,
}: {
  naturaleza: string;
  responsable: string;
  al_elegir_responsable: (valor: string) => void;
  naturaleza_corregida: string;
  al_corregir_naturaleza: (valor: string) => void;
}) {
  const consulta = useQuery({
    queryKey: ["observaciones", "responsables"],
    queryFn: listar_responsables_posibles,
  });
  const rol = _ROL_QUE_RESPONDE[naturaleza_corregida || naturaleza] ?? "";
  const personas = (consulta.data ?? []).filter((persona) =>
    persona.roles.some((rol_persona) => rol_persona === rol),
  );
  return (
    <>
      <Selector
        etiqueta="Corregir naturaleza"
        opciones={[
          { valor: "", etiqueta: "Mantener la naturaleza asignada" },
          { valor: "ADMINISTRATIVA", etiqueta: "Administrativa" },
          { valor: "TECNICA", etiqueta: "Técnica" },
          { valor: "FINANCIERA", etiqueta: "Financiera" },
        ]}
        value={naturaleza_corregida}
        onChange={(evento) => al_corregir_naturaleza(evento.target.value)}
      />
      <Selector
        etiqueta="Responsable"
        opciones={[
          { valor: "", etiqueta: "Sin persona asignada" },
          ...personas.map((persona) => ({ valor: String(persona.id), etiqueta: persona.nombres })),
        ]}
        value={responsable}
        onChange={(evento) => al_elegir_responsable(evento.target.value)}
      />
    </>
  );
}

function usar_asignacion(cuenta_id: number, observacion: Observacion, al_asignar: () => void) {
  const cliente_consultas = useQueryClient();
  const [responsable, set_responsable] = useState(
    observacion.responsable_usuario_id ? String(observacion.responsable_usuario_id) : "",
  );
  const [naturaleza_corregida, set_naturaleza_corregida] = useState("");
  const mutacion = useMutation({
    mutationFn: () =>
      asignar_responsable_observacion(observacion.id, {
        responsable_usuario_id: responsable ? Number(responsable) : null,
        naturaleza_corregida:
          naturaleza_corregida === "" ? null : (naturaleza_corregida as Naturaleza),
      }),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_asignar();
    },
  });
  // Otra naturaleza la responde otro rol: la persona elegida deja de valer.
  const corregir_naturaleza = (valor: string) => {
    set_naturaleza_corregida(valor);
    set_responsable("");
  };
  return { responsable, set_responsable, naturaleza_corregida, corregir_naturaleza, mutacion };
}

export function DialogoAsignarObservacion({
  cuenta_id,
  observacion,
  al_cerrar,
  al_asignar,
}: Propiedades) {
  const { responsable, set_responsable, naturaleza_corregida, corregir_naturaleza, mutacion } =
    usar_asignacion(cuenta_id, observacion, al_asignar);

  return (
    <Dialogo
      titulo="Asignar responsable de la observación"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending}
          >
            Confirmar
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo asignar." />
      <CamposAsignarObservacion
        naturaleza={observacion.naturaleza}
        responsable={responsable}
        al_elegir_responsable={set_responsable}
        naturaleza_corregida={naturaleza_corregida}
        al_corregir_naturaleza={corregir_naturaleza}
      />
    </Dialogo>
  );
}
