import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  listar_respuestas_correo,
  responder_correo_iafas,
  type RespuestaCorreo,
} from "../../api/correos_iafas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "./comunicaciones.module.css";

function FilaRespuesta({ respuesta }: { respuesta: RespuestaCorreo }) {
  const envio = respuesta.enviada_en
    ? `enviada el ${formatear_fecha_hora(respuesta.enviada_en)}`
    : "enviándose";
  return (
    <li>
      <pre className={estilos.texto_correo}>{respuesta.texto}</pre>
      <span className={estilos.dato_secundario}>
        {respuesta.respondido_por}, {envio}
      </span>
    </li>
  );
}

// Lo que la clínica le contestó a la IAFAS por este correo y, para quien
// puede responder, el campo para contestar desde el sistema.
export function RespuestasCorreo({ correo_id }: { correo_id: number }) {
  const cliente_consultas = useQueryClient();
  const { sesion } = usar_sesion();
  const [texto, set_texto] = useState("");
  const clave = ["correos_iafas", correo_id, "respuestas"];
  const respuestas = useQuery({
    queryKey: clave,
    queryFn: () => listar_respuestas_correo(correo_id),
    // Mientras una respuesta está saliendo se vuelve a consultar.
    refetchInterval: (consulta) =>
      (consulta.state.data ?? []).some((r) => !r.enviada_en) ? 3000 : false,
  });
  const envio = useMutation({
    mutationFn: () => responder_correo_iafas(correo_id, texto),
    onSuccess: () => {
      set_texto("");
      void cliente_consultas.invalidateQueries({ queryKey: clave });
    },
  });
  const puede_responder = Boolean(
    sesion?.roles.includes("analista") || sesion?.roles.includes("jefe"),
  );
  return (
    <>
      {(respuestas.data ?? []).length > 0 ? (
        <ul className={estilos.adjuntos}>
          {(respuestas.data ?? []).map((r) => (
            <FilaRespuesta key={r.id} respuesta={r} />
          ))}
        </ul>
      ) : null}
      {puede_responder ? (
        <div className={estilos.fila_resolver}>
          <CampoTexto
            etiqueta="Respuesta al remitente"
            value={texto}
            onChange={(evento) => set_texto(evento.target.value)}
          />
          <Boton
            variante="secundario"
            onClick={() => envio.mutate()}
            disabled={envio.isPending || !texto.trim()}
          >
            Responder
          </Boton>
        </div>
      ) : null}
      <MensajeErrorMutacion error={envio.error} texto_por_defecto="No se pudo responder." />
    </>
  );
}
