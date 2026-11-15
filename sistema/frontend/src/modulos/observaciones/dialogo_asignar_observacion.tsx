import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { asignar_responsable_observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";

interface Propiedades {
  cuenta_id: number;
  observacion_id: number;
  al_cerrar: () => void;
  al_asignar: () => void;
}

function CamposAsignarObservacion({
  responsable_usuario_id,
  set_responsable_usuario_id,
  naturaleza_corregida,
  set_naturaleza_corregida,
}: {
  responsable_usuario_id: string;
  set_responsable_usuario_id: (valor: string) => void;
  naturaleza_corregida: string;
  set_naturaleza_corregida: (valor: string) => void;
}) {
  return (
    <>
      <CampoTexto
        etiqueta="Usuario responsable (id)"
        type="number"
        value={responsable_usuario_id}
        onChange={(evento) => set_responsable_usuario_id(evento.target.value)}
      />
      <Selector
        etiqueta="Corregir naturaleza"
        opciones={[
          { valor: "", etiqueta: "Mantener la naturaleza asignada" },
          { valor: "ADMINISTRATIVA", etiqueta: "Administrativa" },
          { valor: "TECNICA", etiqueta: "Técnica" },
          { valor: "FINANCIERA", etiqueta: "Financiera" },
        ]}
        value={naturaleza_corregida}
        onChange={(evento) => set_naturaleza_corregida(evento.target.value)}
      />
    </>
  );
}

function usar_mutacion_asignar(
  cuenta_id: number,
  observacion_id: number,
  responsable_usuario_id: string,
  naturaleza_corregida: string,
  al_asignar: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () =>
      asignar_responsable_observacion(observacion_id, {
        responsable_usuario_id: responsable_usuario_id ? Number(responsable_usuario_id) : null,
        naturaleza_corregida:
          naturaleza_corregida === ""
            ? null
            : (naturaleza_corregida as "ADMINISTRATIVA" | "TECNICA" | "FINANCIERA"),
      }),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_asignar();
    },
  });
}

export function DialogoAsignarObservacion({
  cuenta_id,
  observacion_id,
  al_cerrar,
  al_asignar,
}: Propiedades) {
  const [responsable_usuario_id, set_responsable_usuario_id] = useState("");
  const [naturaleza_corregida, set_naturaleza_corregida] = useState("");
  const mutacion = usar_mutacion_asignar(
    cuenta_id,
    observacion_id,
    responsable_usuario_id,
    naturaleza_corregida,
    al_asignar,
  );

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
        responsable_usuario_id={responsable_usuario_id}
        set_responsable_usuario_id={set_responsable_usuario_id}
        naturaleza_corregida={naturaleza_corregida}
        set_naturaleza_corregida={set_naturaleza_corregida}
      />
    </Dialogo>
  );
}
