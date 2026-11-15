import { useEffect, useState } from "react";

// Ancho real del contenedor, para dibujar el SVG en pixeles (con un
// viewBox fijo el texto del eje se estiraria con la tarjeta). Ref por
// funcion, no useRef: el elemento puede aparecer despues del primer
// render (cuando llegan los datos) y el observador debe engancharse ahi.
export function usar_ancho<T extends HTMLElement>(): {
  referencia: (elemento: T | null) => void;
  ancho: number;
} {
  const [elemento, set_elemento] = useState<T | null>(null);
  const [ancho, set_ancho] = useState(0);

  useEffect(() => {
    if (!elemento) return;
    const observador = new ResizeObserver((entradas) => {
      set_ancho(entradas[0]?.contentRect.width ?? 0);
    });
    observador.observe(elemento);
    return () => observador.disconnect();
  }, [elemento]);

  return { referencia: set_elemento, ancho };
}
