import { useEffect, useState } from "react";

// Devuelve "valor" con retraso: se actualiza solo cuando el usuario deja de
// escribir por "retraso_ms" (por defecto 400ms). Uso tipico: busqueda en
// vivo que no dispara una peticion por cada tecla.
export function usar_valor_diferido<T>(valor: T, retraso_ms = 400): T {
  const [valor_diferido, set_valor_diferido] = useState(valor);

  useEffect(() => {
    const temporizador = setTimeout(() => set_valor_diferido(valor), retraso_ms);
    return () => clearTimeout(temporizador);
  }, [valor, retraso_ms]);

  return valor_diferido;
}
