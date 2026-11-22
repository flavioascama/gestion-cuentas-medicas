import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { resolver_anulacion } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  solicitud_id: number;
  cuenta_medica_id: number;
  aprobada: boolean;
  al_cerrar: () => void;
  al_resolver: () => void;
}

const _CONSECUENCIA: Record<string, string> = {
  true: "La cuenta pasará al estado Anulada. Esta acción no se puede revertir.",
  false: "La cuenta conserva su estado actual. Esta acción no se puede revertir.",
};

// El motivo es obligatorio al rechazar y opcional al aprobar.
export function DialogoResolverAnulacion({
  solicitud_id,
  cuenta_medica_id,
  aprobada,
  al_cerrar,
  al_resolver,
}: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [motivo, set_motivo] = useState("");
  const mutacion = useMutation({
    mutationFn: () => resolver_anulacion(solicitud_id, aprobada, motivo),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["anulaciones", "pendientes"] });
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_medica_id] });
      al_resolver();
    },
  });
  return (
    <Dialogo
      titulo={aprobada ? "Aprobar la anulación" : "Rechazar la anulación"}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="destructivo"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || (!aprobada && !motivo.trim())}
          >
            {aprobada ? "Aprobar" : "Rechazar"}
          </Boton>
        </>
      }
    >
      <p>{_CONSECUENCIA[String(aprobada)]}</p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo resolver." />
      <CampoTexto
        etiqueta="Motivo"
        obligatorio={!aprobada}
        value={motivo}
        maxLength={500}
        onChange={(evento) => set_motivo(evento.target.value)}
      />
    </Dialogo>
  );
}
