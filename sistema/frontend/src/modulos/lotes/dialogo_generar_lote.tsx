import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { generar_lote, type RespuestaGenerarLote } from "../../api/lotes";
import { FormularioGenerarLote } from "./formulario_generar_lote";
import { ResultadoGeneracionLote } from "./resultado_generacion_lote";
import { usar_formulario_generar_lote } from "./usar_formulario_generar_lote";

interface Propiedades {
  al_cerrar: () => void;
  al_generar_conforme: (lote_id: number) => void;
}

export function DialogoGenerarLote({ al_cerrar, al_generar_conforme }: Propiedades) {
  const [resultado, set_resultado] = useState<RespuestaGenerarLote | null>(null);
  const formulario = usar_formulario_generar_lote();

  const mutacion = useMutation({
    mutationFn: () =>
      generar_lote({
        iafas_id: Number(formulario.iafas_id),
        periodo: formulario.periodo,
        cuenta_ids: formulario.cuenta_ids,
      }),
    onSuccess: (respuesta) => set_resultado(respuesta),
  });

  if (resultado) {
    return (
      <ResultadoGeneracionLote
        resultado={resultado}
        al_cerrar={al_cerrar}
        al_ver_lote={al_generar_conforme}
      />
    );
  }

  return (
    <FormularioGenerarLote
      formulario={formulario}
      generando={mutacion.isPending}
      error={mutacion.error}
      al_generar={() => mutacion.mutate()}
      al_cerrar={al_cerrar}
    />
  );
}
