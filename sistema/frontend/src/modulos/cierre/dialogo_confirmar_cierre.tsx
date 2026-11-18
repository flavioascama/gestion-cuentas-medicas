import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cerrar_cuenta } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
  al_confirmar: () => void;
}

export function DialogoConfirmarCierre({ cuenta_id, al_cerrar, al_confirmar }: Propiedades) {
  const cliente_consultas = useQueryClient();

  const mutacion = useMutation({
    mutationFn: () => cerrar_cuenta(cuenta_id),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_confirmar();
    },
  });

  return (
    <Dialogo
      titulo="Cerrar la cuenta médica"
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
            Cerrar cuenta
          </Boton>
        </>
      }
    >
      <p>La cuenta quedará cerrada y ya no se podrá modificar. Esta acción no se puede deshacer.</p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo cerrar." />
    </Dialogo>
  );
}
