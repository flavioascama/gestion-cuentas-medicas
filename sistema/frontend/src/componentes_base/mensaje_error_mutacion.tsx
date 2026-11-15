import { ErrorApi } from "../api/cliente_http";
import { Mensaje } from "./mensaje";

interface Propiedades {
  error: unknown;
  texto_por_defecto: string;
}

// Patron repetido en cada mutacion del proyecto: mostrar el mensaje del
// backend si el error viene de la API, o un texto generico si no.
export function MensajeErrorMutacion({ error, texto_por_defecto }: Propiedades) {
  if (!error) return null;
  return (
    <Mensaje tipo="error" texto={error instanceof ErrorApi ? error.message : texto_por_defecto} />
  );
}
