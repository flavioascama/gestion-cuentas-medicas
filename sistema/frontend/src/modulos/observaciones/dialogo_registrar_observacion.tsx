import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { registrar_observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";
import { usar_motivos_observacion } from "./usar_observaciones";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
  al_registrar: () => void;
}

interface CamposFormulario {
  motivo_codigo: string;
  set_motivo_codigo: (valor: string) => void;
  es_parcial: boolean;
  set_es_parcial: (valor: boolean) => void;
  detalle_campo_objetado: string;
  set_detalle_campo_objetado: (valor: string) => void;
  monto_observado: string;
  set_monto_observado: (valor: string) => void;
}

function CamposRegistrarObservacion({ campos }: { campos: CamposFormulario }) {
  const consulta_motivos = usar_motivos_observacion();

  return (
    <>
      <Selector
        etiqueta="Motivo indicado por la IAFAS"
        obligatorio
        opciones={[
          { valor: "", etiqueta: "Seleccione un motivo" },
          ...(consulta_motivos.data ?? []).map((m) => ({
            valor: m.codigo,
            etiqueta: `${m.codigo} — ${m.descripcion}`,
          })),
        ]}
        value={campos.motivo_codigo}
        onChange={(evento) => campos.set_motivo_codigo(evento.target.value)}
      />
      <Selector
        etiqueta="Alcance de la observación"
        obligatorio
        opciones={[
          { valor: "total", etiqueta: "Total: la IAFAS objeta toda la cuenta" },
          { valor: "parcial", etiqueta: "Parcial: objeta una parte; el resto sigue a liquidación" },
        ]}
        value={campos.es_parcial ? "parcial" : "total"}
        onChange={(evento) => campos.set_es_parcial(evento.target.value === "parcial")}
      />
      <CampoTexto
        etiqueta="Dato observado por la IAFAS (opcional)"
        value={campos.detalle_campo_objetado}
        onChange={(evento) => campos.set_detalle_campo_objetado(evento.target.value)}
      />
      <CampoTexto
        etiqueta={campos.es_parcial ? "Monto observado" : "Monto observado (opcional)"}
        obligatorio={campos.es_parcial}
        type="number"
        min="0.01"
        step="0.01"
        value={campos.monto_observado}
        onChange={(evento) => campos.set_monto_observado(evento.target.value)}
        error={
          campos.monto_observado !== "" && !(Number(campos.monto_observado) > 0)
            ? "El monto debe ser mayor que S/ 0.00."
            : undefined
        }
      />
    </>
  );
}

function usar_campos_registro(): CamposFormulario {
  const [motivo_codigo, set_motivo_codigo] = useState("");
  const [es_parcial, set_es_parcial] = useState(false);
  const [detalle_campo_objetado, set_detalle_campo_objetado] = useState("");
  const [monto_observado, set_monto_observado] = useState("");
  return {
    motivo_codigo,
    set_motivo_codigo,
    es_parcial,
    set_es_parcial,
    detalle_campo_objetado,
    set_detalle_campo_objetado,
    monto_observado,
    set_monto_observado,
  };
}

export function DialogoRegistrarObservacion({ cuenta_id, al_cerrar, al_registrar }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const campos = usar_campos_registro();
  // El monto, si se escribe, es mayor que 0; la glosa parcial lo exige.
  const monto_no_valido =
    (campos.es_parcial && campos.monto_observado === "") ||
    (campos.monto_observado !== "" && !(Number(campos.monto_observado) > 0));

  const mutacion = useMutation({
    mutationFn: () =>
      registrar_observacion(cuenta_id, {
        motivo_codigo: campos.motivo_codigo,
        es_parcial: campos.es_parcial,
        detalle_campo_objetado: campos.detalle_campo_objetado || null,
        monto_observado: campos.monto_observado || null,
      }),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      void cliente_consultas.invalidateQueries({ queryKey: ["plazos"] });
      al_registrar();
    },
  });

  return (
    <Dialogo
      titulo="Registrar observación de la IAFAS"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || !campos.motivo_codigo || monto_no_valido}
          >
            Registrar observación
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo registrar." />
      <CamposRegistrarObservacion campos={campos} />
    </Dialogo>
  );
}
