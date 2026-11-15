import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { solicitar_anulacion } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
  al_solicitar: () => void;
}

export function DialogoSolicitarAnulacion({ cuenta_id, al_cerrar, al_solicitar }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [motivo, set_motivo] = useState("");

  const mutacion = useMutation({
    mutationFn: () => solicitar_anulacion(cuenta_id, motivo),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_solicitar();
    },
  });

  return (
    <Dialogo
      titulo="Solicitar la anulación de la cuenta"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="destructivo"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || !motivo}
          >
            Solicitar anulación
          </Boton>
        </>
      }
    >
      <p>La solicitud queda pendiente de la aprobación del jefe de cuentas médicas.</p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo solicitar." />
      <CampoTexto
        etiqueta="Motivo"
        value={motivo}
        onChange={(evento) => set_motivo(evento.target.value)}
      />
    </Dialogo>
  );
}
