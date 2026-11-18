import { useState } from "react";
import { ErrorApi } from "../../api/cliente_http";
import { usar_sesion } from "../../sesion/contexto_sesion";

const _POLITICA =
  "La contraseña debe tener al menos doce caracteres, con una mayúscula, una minúscula y un dígito.";

// Lo que responde el servidor, dicho como en el resto de la pantalla.
const _MENSAJES = new Map<string, string>([
  ["CLAVE_ACTUAL_INCORRECTA", "La contraseña actual no es correcta."],
  ["CLAVE_REPETIDA", "La contraseña nueva debe ser distinta de la actual."],
  ["CLAVE_DEBIL", _POLITICA],
]);

function cumple_politica(clave: string): boolean {
  return clave.length >= 12 && /[A-Z]/.test(clave) && /[a-z]/.test(clave) && /\d/.test(clave);
}

function mensaje_de(motivo: unknown): string {
  if (!(motivo instanceof ErrorApi)) return "No se pudo cambiar la contraseña.";
  return _MENSAJES.get(motivo.codigo) ?? motivo.message;
}

// Cambio de la contraseña propia (2026-11-18): lo usan el dialogo del menu
// de perfil y la pantalla del primer ingreso con una contraseña temporal.
export function usar_cambio_clave(al_terminar?: () => void) {
  const { cambiar_clave } = usar_sesion();
  const [clave_actual, set_clave_actual] = useState("");
  const [clave_nueva, set_clave_nueva] = useState("");
  const [repetida, set_repetida] = useState("");
  const [error, set_error] = useState<string | null>(null);
  const [enviando, set_enviando] = useState(false);

  const enviar = () => {
    if (repetida !== clave_nueva) return set_error("Las contraseñas nuevas no coinciden.");
    if (!cumple_politica(clave_nueva)) return set_error(_POLITICA);
    set_error(null);
    set_enviando(true);
    cambiar_clave(clave_actual, clave_nueva)
      .then(() => al_terminar?.())
      .catch((motivo: unknown) => {
        set_error(mensaje_de(motivo));
        set_enviando(false);
      });
  };

  return {
    clave_actual,
    set_clave_actual,
    clave_nueva,
    set_clave_nueva,
    repetida,
    set_repetida,
    error,
    enviando,
    completo: clave_actual !== "" && clave_nueva !== "" && repetida !== "",
    enviar,
  };
}

export type CambioClave = ReturnType<typeof usar_cambio_clave>;
