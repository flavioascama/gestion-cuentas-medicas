import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  cuenta_id: number;
  titulo: string;
  texto: string;
  texto_error: string;
  quitar: () => Promise<unknown>;
  al_cerrar: () => void;
}

// Confirmacion antes de quitar un procedimiento o un producto de la cuenta
// (mismo dialogo que el cierre de la cuenta).
export function DialogoConfirmarQuitar(propiedades: Propiedades) {
  const { cuenta_id, al_cerrar } = propiedades;
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: propiedades.quitar,
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_cerrar();
    },
  });

  return (
    <Dialogo
      titulo={propiedades.titulo}
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
            Quitar
          </Boton>
        </>
      }
    >
      <p>{propiedades.texto}</p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto={propiedades.texto_error} />
    </Dialogo>
  );
}
