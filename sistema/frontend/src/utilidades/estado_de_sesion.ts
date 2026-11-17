import { useCallback, useState } from "react";

// Estado de una pantalla que debe sobrevivir a la navegacion dentro de la
// misma pestana del navegador: al abrir un detalle y volver, la bandeja
// conserva sus filtros. Se guarda en sessionStorage (se borra al cerrar la
// pestana) y se olvida al iniciar o cerrar sesion.

const _PREFIJO = "estado_pantalla:";

function leer<T>(clave: string): T | null {
  try {
    const crudo = sessionStorage.getItem(_PREFIJO + clave);
    return crudo === null ? null : (JSON.parse(crudo) as T);
  } catch {
    return null;
  }
}

function guardar<T>(clave: string, valor: T): void {
  try {
    sessionStorage.setItem(_PREFIJO + clave, JSON.stringify(valor));
  } catch {
    // Almacenamiento lleno o bloqueado: el estado sigue en memoria.
  }
}

// Como useState. `prioritario`, si no es null, manda sobre lo guardado
// (por ejemplo, los filtros que llegan en la direccion de un enlace).
export function usar_estado_de_sesion<T>(
  clave: string,
  inicial: T,
  prioritario: T | null = null,
): readonly [T, (nuevo: T) => void] {
  const [valor, set_valor] = useState<T>(() => {
    if (prioritario === null) return leer<T>(clave) ?? inicial;
    guardar(clave, prioritario);
    return prioritario;
  });
  const cambiar = useCallback(
    (nuevo: T) => {
      set_valor(nuevo);
      guardar(clave, nuevo);
    },
    [clave],
  );
  return [valor, cambiar] as const;
}

// Los filtros de una persona no deben quedar para la siguiente que use la
// misma pestana.
export function olvidar_estados_de_sesion(): void {
  try {
    for (const clave of Object.keys(sessionStorage)) {
      if (clave.startsWith(_PREFIJO)) sessionStorage.removeItem(clave);
    }
  } catch {
    // Sin acceso al almacenamiento no hay nada guardado que olvidar.
  }
}
