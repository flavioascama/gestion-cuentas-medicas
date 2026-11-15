import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { responder_observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  cuenta_id: number;
  observacion_id: number;
  al_cerrar: () => void;
  al_responder: () => void;
}

function CamposResponderObservacion({
  respuesta_texto,
  set_respuesta_texto,
  respuesta_sustento,
  set_respuesta_sustento,
}: {
  respuesta_texto: string;
  set_respuesta_texto: (valor: string) => void;
  respuesta_sustento: string;
  set_respuesta_sustento: (valor: string) => void;
}) {
  return (
    <>
      <CampoTexto
        etiqueta="Respuesta a la IAFAS (subsanación)"
        value={respuesta_texto}
        onChange={(evento) => set_respuesta_texto(evento.target.value)}
      />
      <CampoTexto
        etiqueta="Sustento"
        value={respuesta_sustento}
        onChange={(evento) => set_respuesta_sustento(evento.target.value)}
      />
    </>
  );
}

export function DialogoResponderObservacion({
  cuenta_id,
  observacion_id,
  al_cerrar,
  al_responder,
}: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [respuesta_texto, set_respuesta_texto] = useState("");
  const [respuesta_sustento, set_respuesta_sustento] = useState("");

  const mutacion = useMutation({
    mutationFn: () =>
      responder_observacion(observacion_id, {
        respuesta_texto,
        respuesta_sustento: respuesta_sustento || null,
      }),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_responder();
    },
  });

  return (
    <Dialogo
      titulo="Responder la observación de la IAFAS"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || !respuesta_texto}
          >
            Registrar respuesta
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo responder." />
      <CamposResponderObservacion
        respuesta_texto={respuesta_texto}
        set_respuesta_texto={set_respuesta_texto}
        respuesta_sustento={respuesta_sustento}
        set_respuesta_sustento={set_respuesta_sustento}
      />
    </Dialogo>
  );
}
