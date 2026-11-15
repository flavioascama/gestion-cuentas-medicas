import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resolver_anulacion } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  solicitud_id: number;
  cuenta_medica_id: number;
  aprobada: boolean;
  al_cerrar: () => void;
  al_resolver: () => void;
}

export function DialogoResolverAnulacion({
  solicitud_id,
  cuenta_medica_id,
  aprobada,
  al_cerrar,
  al_resolver,
}: Propiedades) {
  const cliente_consultas = useQueryClient();

  const mutacion = useMutation({
    mutationFn: () => resolver_anulacion(solicitud_id, aprobada),
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
            disabled={mutacion.isPending}
          >
            {aprobada ? "Aprobar" : "Rechazar"}
          </Boton>
        </>
      }
    >
      <p>
        {aprobada
          ? "La cuenta pasará al estado ANULADA. Esta acción no se puede revertir."
          : "La cuenta conserva su estado actual. Esta acción no se puede revertir."}
      </p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo resolver." />
    </Dialogo>
  );
}
