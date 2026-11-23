import type { Usuario } from "../../api/usuarios";
import { BotonConConfirmacion } from "../../componentes_base/dialogo_confirmar";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_eliminar_usuario } from "./usar_usuarios";

// Eliminar un usuario creado por error: el servidor solo lo permite si
// nunca tuvo actividad; el que ya trabajó se desactiva.
export function BotonEliminarUsuario({
  usuario,
  disabled,
}: {
  usuario: Usuario;
  disabled: boolean;
}) {
  const eliminacion = usar_eliminar_usuario();
  return (
    <>
      <BotonConConfirmacion
        variante="terciario"
        disabled={disabled || eliminacion.isPending}
        titulo="Eliminar usuario"
        texto={`Se eliminará ${usuario.nombre_usuario}. Esta acción no se puede deshacer.`}
        texto_confirmar="Eliminar"
        al_confirmar={() => eliminacion.mutate(usuario.id)}
      >
        Eliminar
      </BotonConConfirmacion>
      <MensajeErrorMutacion error={eliminacion.error} texto_por_defecto="No se pudo eliminar." />
    </>
  );
}
