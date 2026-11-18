import type { FormEvent } from "react";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_cambio_clave, type CambioClave } from "./usar_cambio_clave";
import estilos from "./ingreso.module.css";

function CamposCambioClave({ cambio }: { cambio: CambioClave }) {
  return (
    <>
      {cambio.error ? <Mensaje tipo="error" texto={cambio.error} /> : null}
      <CampoTexto
        etiqueta="Contraseña actual"
        type="password"
        autoComplete="current-password"
        value={cambio.clave_actual}
        onChange={(evento) => cambio.set_clave_actual(evento.target.value)}
        autoFocus
      />
      <CampoTexto
        etiqueta="Contraseña nueva"
        type="password"
        autoComplete="new-password"
        value={cambio.clave_nueva}
        onChange={(evento) => cambio.set_clave_nueva(evento.target.value)}
      />
      <CampoTexto
        etiqueta="Repetir la contraseña nueva"
        type="password"
        autoComplete="new-password"
        value={cambio.repetida}
        onChange={(evento) => cambio.set_repetida(evento.target.value)}
      />
    </>
  );
}

// Desde el menu de perfil: cualquier usuario cambia su contraseña.
export function DialogoCambiarClave({ al_cerrar }: { al_cerrar: () => void }) {
  const cambio = usar_cambio_clave(al_cerrar);
  return (
    <Dialogo
      titulo="Cambiar contraseña"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={cambio.enviar}
            disabled={!cambio.completo || cambio.enviando}
          >
            Cambiar contraseña
          </Boton>
        </>
      }
    >
      <CamposCambioClave cambio={cambio} />
    </Dialogo>
  );
}

// Primer ingreso con la contraseña que puso el administrador: hasta
// cambiarla no se entra al sistema (el servidor tampoco lo permite).
export function CambioClaveObligatorio() {
  const { cerrar_sesion } = usar_sesion();
  const cambio = usar_cambio_clave();
  const al_enviar = (evento: FormEvent) => {
    evento.preventDefault();
    cambio.enviar();
  };
  return (
    <div className={estilos.envoltorio}>
      <form className={estilos.tarjeta} onSubmit={al_enviar}>
        <div className={estilos.titulo}>Cambie su contraseña</div>
        <CamposCambioClave cambio={cambio} />
        <Boton
          type="submit"
          variante="primario"
          className={estilos.boton_enviar}
          disabled={!cambio.completo || cambio.enviando}
        >
          Cambiar contraseña
        </Boton>
        <Boton variante="terciario" onClick={() => void cerrar_sesion()}>
          Cerrar sesión
        </Boton>
      </form>
    </div>
  );
}
