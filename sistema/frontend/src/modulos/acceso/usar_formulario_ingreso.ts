import { useState, type FormEvent } from "react";
import { ErrorApi } from "../../api/cliente_http";
import { usar_sesion } from "../../sesion/contexto_sesion";

export function usar_formulario_ingreso(al_ingresar: () => void) {
  const { iniciar_sesion } = usar_sesion();
  const [nombre_usuario, set_nombre_usuario] = useState("");
  const [clave, set_clave] = useState("");
  const [error, set_error] = useState<string | null>(null);
  const [enviando, set_enviando] = useState(false);

  const manejar_envio = (evento: FormEvent) => {
    evento.preventDefault();
    set_error(null);
    set_enviando(true);
    iniciar_sesion(nombre_usuario, clave)
      .then(al_ingresar)
      .catch((motivo: unknown) => {
        set_error(motivo instanceof ErrorApi ? motivo.message : "No se pudo iniciar sesión.");
      })
      .finally(() => set_enviando(false));
  };

  return { nombre_usuario, set_nombre_usuario, clave, set_clave, error, enviando, manejar_envio };
}
