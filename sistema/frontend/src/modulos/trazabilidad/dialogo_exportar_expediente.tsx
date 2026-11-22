import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { exportar_expediente } from "../../api/trazabilidad";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_detalle_cuenta } from "../cuentas/usar_cuentas";
import { abrir_expediente, html_expediente } from "./documento_expediente";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
}

function ResultadoExpediente({
  al_abrir,
  al_cerrar,
}: {
  al_abrir: () => void;
  al_cerrar: () => void;
}) {
  return (
    <Dialogo
      titulo="Exportar expediente de auditoría"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_abrir}>
            Abrir de nuevo
          </Boton>
          <Boton variante="primario" onClick={al_cerrar}>
            Cerrar
          </Boton>
        </>
      }
    >
      <p>Expediente generado.</p>
    </Dialogo>
  );
}

function FormularioExportarExpediente({
  motivo,
  set_motivo,
  error,
  enviando,
  al_exportar,
  al_cerrar,
}: {
  motivo: string;
  set_motivo: (valor: string) => void;
  error: unknown;
  enviando: boolean;
  al_exportar: () => void;
  al_cerrar: () => void;
}) {
  return (
    <Dialogo
      titulo="Exportar expediente de auditoría"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton variante="primario" onClick={al_exportar} disabled={enviando || !motivo}>
            Exportar
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo exportar." />
      <CampoTexto
        etiqueta="Motivo"
        obligatorio
        value={motivo}
        onChange={(evento) => set_motivo(evento.target.value)}
      />
    </Dialogo>
  );
}

export function DialogoExportarExpediente({ cuenta_id, al_cerrar }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const { sesion } = usar_sesion();
  const cuenta = usar_detalle_cuenta(cuenta_id).data;
  const [motivo, set_motivo] = useState("");
  const [documento, set_documento] = useState<string | null>(null);

  const mutacion = useMutation({
    mutationFn: () => exportar_expediente(cuenta_id, motivo),
    onSuccess: (expediente) => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id, "historial"] });
      const html = html_expediente({
        expediente,
        cuenta: cuenta?.identificacion_interna ?? "",
        ipress: cuenta?.ipress_codigo ?? null,
        exportado_por: sesion?.nombres ?? sesion?.nombre_usuario ?? "",
        motivo,
      });
      set_documento(html);
      abrir_expediente(html);
    },
  });

  if (documento !== null) {
    return (
      <ResultadoExpediente al_abrir={() => abrir_expediente(documento)} al_cerrar={al_cerrar} />
    );
  }
  return (
    <FormularioExportarExpediente
      motivo={motivo}
      set_motivo={set_motivo}
      error={mutacion.error}
      enviando={mutacion.isPending}
      al_exportar={() => mutacion.mutate()}
      al_cerrar={al_cerrar}
    />
  );
}
