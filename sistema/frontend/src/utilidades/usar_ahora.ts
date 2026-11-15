import { useEffect, useState } from "react";

// Instante actual que se renueva solo cada `intervalo_ms`: para textos
// relativos ("hace 5 min") que deben avanzar aunque los datos no cambien
// (una consulta que vuelve igual no vuelve a pintar la pantalla).
export function usar_ahora(intervalo_ms = 30_000): number {
  const [ahora, set_ahora] = useState(() => Date.now());
  useEffect(() => {
    const temporizador = setInterval(() => set_ahora(Date.now()), intervalo_ms);
    return () => clearInterval(temporizador);
  }, [intervalo_ms]);
  return ahora;
}
