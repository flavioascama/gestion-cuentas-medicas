import type { NombreRol } from "../../api/auth";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { roles_de_perfiles } from "../../componentes_base/mapa_roles";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { CamposUsuario } from "./campos_usuario";
import { usar_actualizar_usuario, usar_crear_usuario } from "./usar_usuarios";
import { usar_formulario_usuario } from "./usar_formulario_usuario";

interface Propiedades {
  usuario: Usuario | null;
  al_cerrar: () => void;
}

// Sus propios roles los cambia otro administrador: solo se envia el nombre.
function solicitud_edicion(
  formulario: ReturnType<typeof usar_formulario_usuario>,
  roles: NombreRol[],
) {
  const { nombres } = formulario;
  return formulario.es_propio ? { nombres } : { nombres, roles };
}

export function DialogoUsuario({ usuario, al_cerrar }: Propiedades) {
  const formulario = usar_formulario_usuario(usuario);
  const mutacion_crear = usar_crear_usuario();
  const mutacion_actualizar = usar_actualizar_usuario();
  const guardando = mutacion_crear.isPending || mutacion_actualizar.isPending;
  const error = mutacion_crear.error ?? mutacion_actualizar.error;

  const guardar = () => {
    const roles = roles_de_perfiles(Array.from(formulario.roles));
    if (usuario) {
      mutacion_actualizar.mutate(
        { usuario_id: usuario.id, solicitud: solicitud_edicion(formulario, roles) },
        { onSuccess: al_cerrar },
      );
    } else {
      mutacion_crear.mutate(
        {
          nombre_usuario: formulario.nombre_usuario,
          clave: formulario.clave,
          nombres: formulario.nombres,
          roles,
        },
        { onSuccess: al_cerrar },
      );
    }
  };

  return (
    <Dialogo
      titulo={usuario ? `Editar usuario: ${usuario.nombre_usuario}` : "Crear usuario"}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={guardar}
            disabled={guardando || formulario.falta_completar}
          >
            Guardar
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo guardar el usuario." />
      <CamposUsuario formulario={formulario} />
    </Dialogo>
  );
}
