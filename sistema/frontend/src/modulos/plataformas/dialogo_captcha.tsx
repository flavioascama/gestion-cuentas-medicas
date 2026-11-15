import { useState } from "react";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_imagen_captcha } from "./usar_imagen_captcha";
import { usar_responder_captcha } from "./usar_responder_captcha";
import estilos from "./dialogo_captcha.module.css";

interface Propiedades {
  sesion_id: number;
  plataforma: string;
  al_cerrar: () => void;
}

export function DialogoCaptcha({ sesion_id, plataforma, al_cerrar }: Propiedades) {
  const [respuesta, set_respuesta] = useState("");
  const url_imagen = usar_imagen_captcha(sesion_id);
  const mutacion = usar_responder_captcha(sesion_id, plataforma, al_cerrar, () =>
    set_respuesta(""),
  );

  return (
    <Dialogo
      titulo="Responder CAPTCHA"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate(respuesta)}
            disabled={mutacion.isPending || !respuesta}
          >
            Enviar respuesta
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="La respuesta no fue aceptada. Intente de nuevo."
      />
      {url_imagen ? (
        <img className={estilos.imagen_captcha} src={url_imagen} alt="Imagen de verificación" />
      ) : (
        <p>Cargando imagen…</p>
      )}
      <CampoTexto
        etiqueta="Texto de la imagen"
        value={respuesta}
        onChange={(evento) => set_respuesta(evento.target.value)}
        autoFocus
      />
    </Dialogo>
  );
}
