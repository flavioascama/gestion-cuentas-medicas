import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { exportar_expediente, type Expediente } from "../../api/trazabilidad";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { formatear_fecha_hora } from "../../utilidades/formato";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
}

function ResultadoExpediente({
  expediente,
  al_cerrar,
}: {
  expediente: Expediente;
  al_cerrar: () => void;
}) {
  const documentos =
    expediente.documentos.length === 0
      ? "ninguno"
      : expediente.documentos.map((d) => `${d.tipo} (${d.referencia})`).join(", ");

  return (
    <Dialogo
      titulo="Expediente exportado"
      al_cerrar={al_cerrar}
      acciones={
        <Boton variante="primario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      <p>Generado el {formatear_fecha_hora(expediente.generado_en)}.</p>
      <p>
        Eventos incluidos: {expediente.historial.eventos.length}. Documentos asociados: {documentos}
        .
      </p>
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
      <p>Registre el motivo de la exportación. Queda asociado a la bitácora de accesos.</p>
      <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo exportar." />
      <CampoTexto
        etiqueta="Motivo"
        value={motivo}
        onChange={(evento) => set_motivo(evento.target.value)}
      />
    </Dialogo>
  );
}

export function DialogoExportarExpediente({ cuenta_id, al_cerrar }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [motivo, set_motivo] = useState("");

  const mutacion = useMutation({
    mutationFn: () => exportar_expediente(cuenta_id, motivo),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id, "historial"] });
    },
  });

  if (mutacion.isSuccess) {
    return <ResultadoExpediente expediente={mutacion.data} al_cerrar={al_cerrar} />;
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
