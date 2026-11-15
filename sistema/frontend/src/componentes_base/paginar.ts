import { useState } from "react";

// Paginacion del lado del cliente (decision explicita del usuario,
// frente a paginacion real en el backend): las bandejas ya traen el
// listado completo ya filtrado por el servidor (estado/IAFAS/fecha o
// periodo); esto solo corta ese arreglo en paginas para no mostrarlo
// todo de golpe. No reduce lo que viaja por red -- si el volumen real
// de datos creciera mucho, la paginacion de verdad (limite/desplazamiento
// en el API) queda como mejora futura, no resuelta aqui.

export const TAMANIO_PAGINA = 25;

export function calcular_total_paginas(cantidad_registros: number, tamanio_pagina: number): number {
  return Math.max(Math.ceil(cantidad_registros / tamanio_pagina), 1);
}

export function paginar<T>(filas: T[], pagina: number, tamanio_pagina: number): T[] {
  const inicio = (pagina - 1) * tamanio_pagina;
  return filas.slice(inicio, inicio + tamanio_pagina);
}

// Agrupa el calculo que cada bandeja repetiria igual (pagina actual
// acotada al total real, el slice de la pagina, el total de paginas):
// una sola llamada en vez de cuatro lineas de aritmetica por pantalla.
export function usar_pagina_cliente<T>(filas: T[]) {
  const [pagina, set_pagina] = useState(1);
  const total_paginas = calcular_total_paginas(filas.length, TAMANIO_PAGINA);
  const pagina_actual = Math.min(pagina, total_paginas);
  return {
    pagina_actual,
    total_paginas,
    filas_pagina: paginar(filas, pagina_actual, TAMANIO_PAGINA),
    set_pagina,
  };
}
