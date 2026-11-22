import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  disponibilidad_validacion_contingencia,
  registrar_validacion_contingencia,
} from "../../api/contingencia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { leer_base64 } from "../../utilidades/archivo";
import estilos from "./contingencia.module.css";

// CU-03, flujo alternativo ("si el validador no esta disponible, se aplica
// el modo de contingencia"; RF-23, C-18). VALIDADO exige el .S01 que el
// validador entrego por otro medio: el sistema nunca lo genera (RI-05).

type Resultado = "VALIDADO" | "OBSERVADO";

// Las cotas del servidor para el sustento.
const _SUSTENTO_MINIMO = 10;
const _SUSTENTO_MAXIMO = 1000;

const _OPCIONES = [
  { valor: "VALIDADO", etiqueta: "Validado (adjuntar el .S01)" },
  { valor: "OBSERVADO", etiqueta: "Observado por el validador" },
];

function usar_registro(lote_id: number, al_cerrar: () => void) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: async (datos: { resultado: Resultado; sustento: string; archivo: File | null }) =>
      registrar_validacion_contingencia(lote_id, {
        resultado: datos.resultado,
        sustento: datos.sustento,
        nombre_s01: datos.archivo?.name ?? null,
        contenido_s01_base64: datos.archivo ? await leer_base64(datos.archivo) : null,
      }),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] });
      al_cerrar();
    },
  });
}

function CamposResultado({
  resultado,
  al_cambiar_resultado,
  al_cambiar_archivo,
}: {
  resultado: Resultado;
  al_cambiar_resultado: (valor: Resultado) => void;
  al_cambiar_archivo: (archivo: File | null) => void;
}) {
  return (
    <>
      <Selector
        etiqueta="Resultado del validador"
        obligatorio
        opciones={_OPCIONES}
        value={resultado}
        onChange={(evento) => al_cambiar_resultado(evento.target.value as Resultado)}
      />
      {resultado === "VALIDADO" ? (
        <label className={estilos.campo_archivo}>
          Archivo de transmisión (.S01) *
          <input
            type="file"
            accept=".S01,.s01"
            onChange={(evento) => al_cambiar_archivo(evento.target.files?.[0] ?? null)}
          />
        </label>
      ) : null}
    </>
  );
}

function DialogoValidacionContingencia({
  lote_id,
  al_cerrar,
}: {
  lote_id: number;
  al_cerrar: () => void;
}) {
  const [resultado, set_resultado] = useState<Resultado>("VALIDADO");
  const [sustento, set_sustento] = useState("");
  const [archivo, set_archivo] = useState<File | null>(null);
  const mutacion = usar_registro(lote_id, al_cerrar);
  const listo =
    sustento.trim().length >= _SUSTENTO_MINIMO && (resultado === "OBSERVADO" || archivo !== null);

  return (
    <Dialogo
      titulo="Registrar la validación en modo de contingencia"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate({ resultado, sustento, archivo })}
            disabled={mutacion.isPending || !listo}
          >
            Registrar en contingencia
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo registrar." />
      <CamposResultado
        resultado={resultado}
        al_cambiar_resultado={set_resultado}
        al_cambiar_archivo={set_archivo}
      />
      <CampoTexto
        etiqueta="Sustento"
        obligatorio
        value={sustento}
        maxLength={_SUSTENTO_MAXIMO}
        onChange={(evento) => set_sustento(evento.target.value)}
      />
    </Dialogo>
  );
}

export function AccionValidacionContingencia({ lote_id }: { lote_id: number }) {
  const { sesion } = usar_sesion();
  const [abierto, set_abierto] = useState(false);
  const consulta = useQuery({
    queryKey: ["lotes", lote_id, "contingencia_validacion"],
    queryFn: () => disponibilidad_validacion_contingencia(lote_id),
    // Tabla 46: registrar en contingencia es solo del analista.
    enabled: !!sesion?.roles.includes("analista"),
  });
  if (!consulta.data?.habilitada) return null;

  return (
    <div className={estilos.aviso} role="status">
      <p className={estilos.texto_aviso}>
        El validador TEDEF Web no respondió tras los reintentos.
      </p>
      <Boton variante="secundario" onClick={() => set_abierto(true)}>
        Registrar en contingencia
      </Boton>
      {abierto ? (
        <DialogoValidacionContingencia lote_id={lote_id} al_cerrar={() => set_abierto(false)} />
      ) : null}
    </div>
  );
}
