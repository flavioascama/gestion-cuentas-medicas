import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adjuntar_documento_respuesta, responder_observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { leer_base64 } from "../../utilidades/archivo";
import estilos from "../cuentas/detalle_cuenta.module.css";

interface Propiedades {
  cuenta_id: number;
  observacion_id: number;
  // Lo que objeto la IAFAS (por ejemplo, "Falta firma en la orden").
  detalle?: string | null;
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
        etiqueta="Respuesta a la IAFAS"
        obligatorio
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

function DatoObservado({ detalle }: { detalle: string | null }) {
  if (!detalle) return null;
  return (
    <div className={estilos.campo_dato}>
      <span className={estilos.etiqueta_dato}>Dato observado</span>
      <span className={estilos.valor_dato}>{detalle}</span>
    </div>
  );
}

interface CamposRespuesta {
  respuesta_texto: string;
  set_respuesta_texto: (valor: string) => void;
  respuesta_sustento: string;
  set_respuesta_sustento: (valor: string) => void;
  // Documento PDF que acompaña la respuesta (opcional).
  adjunto: File | null;
  set_adjunto: (archivo: File | null) => void;
}

function usar_campos_respuesta(): CamposRespuesta {
  const [respuesta_texto, set_respuesta_texto] = useState("");
  const [respuesta_sustento, set_respuesta_sustento] = useState("");
  const [adjunto, set_adjunto] = useState<File | null>(null);
  return {
    respuesta_texto,
    set_respuesta_texto,
    respuesta_sustento,
    set_respuesta_sustento,
    adjunto,
    set_adjunto,
  };
}

function CampoAdjunto({ al_cambiar }: { al_cambiar: (archivo: File | null) => void }) {
  return (
    <label className={estilos.campo_dato}>
      <span className={estilos.etiqueta_dato}>Documento adjunto (PDF)</span>
      <input
        type="file"
        accept=".pdf,application/pdf"
        onChange={(evento) => al_cambiar(evento.target.files?.[0] ?? null)}
      />
    </label>
  );
}

// Primero se sube el documento, si lo hay; después se registra la respuesta.
async function responder_con_adjunto(observacion_id: number, campos: CamposRespuesta) {
  if (campos.adjunto) {
    await adjuntar_documento_respuesta(observacion_id, {
      nombre: campos.adjunto.name,
      contenido_base64: await leer_base64(campos.adjunto),
    });
  }
  await responder_observacion(observacion_id, {
    respuesta_texto: campos.respuesta_texto,
    respuesta_sustento: campos.respuesta_sustento || null,
  });
}

function usar_respuesta(
  cuenta_id: number,
  observacion_id: number,
  campos: CamposRespuesta,
  al_responder: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () => responder_con_adjunto(observacion_id, campos),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      void cliente_consultas.invalidateQueries({ queryKey: ["plazos"] });
      al_responder();
    },
  });
}

export function DialogoResponderObservacion({
  cuenta_id,
  observacion_id,
  detalle = null,
  al_cerrar,
  al_responder,
}: Propiedades) {
  const campos = usar_campos_respuesta();
  const { respuesta_texto, set_respuesta_texto, respuesta_sustento, set_respuesta_sustento } =
    campos;
  const mutacion = usar_respuesta(cuenta_id, observacion_id, campos, al_responder);

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
      <DatoObservado detalle={detalle} />
      <CamposResponderObservacion
        respuesta_texto={respuesta_texto}
        set_respuesta_texto={set_respuesta_texto}
        respuesta_sustento={respuesta_sustento}
        set_respuesta_sustento={set_respuesta_sustento}
      />
      <CampoAdjunto al_cambiar={campos.set_adjunto} />
    </Dialogo>
  );
}
