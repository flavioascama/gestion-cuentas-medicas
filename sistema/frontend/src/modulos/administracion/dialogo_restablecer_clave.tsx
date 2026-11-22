import { useState } from "react";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { _POLITICA, cumple_politica } from "../acceso/usar_cambio_clave";
import { usar_restablecer_clave } from "./usar_usuarios";

export function DialogoRestablecerClave({
  usuario,
  al_cerrar,
}: {
  usuario: Usuario;
  al_cerrar: () => void;
}) {
  const [clave, set_clave] = useState("");
  const mutacion = usar_restablecer_clave();

  return (
    <Dialogo
      titulo={`Restablecer contraseña: ${usuario.nombre_usuario}`}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() =>
              mutacion.mutate({ usuario_id: usuario.id, clave }, { onSuccess: al_cerrar })
            }
            disabled={mutacion.isPending || !cumple_politica(clave)}
          >
            Restablecer
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo restablecer la contraseña."
      />
      <CampoTexto
        etiqueta="Contraseña temporal"
        obligatorio
        type="password"
        value={clave}
        error={clave && !cumple_politica(clave) ? _POLITICA : undefined}
        onChange={(evento) => set_clave(evento.target.value)}
      />
    </Dialogo>
  );
}
