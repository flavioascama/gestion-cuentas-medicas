import { resolver_estado } from "./mapa_estados";
import estilos from "./etiqueta_estado.module.css";

interface Propiedades {
  estado: string;
}

// Rediseno pedido por el usuario (2026-11-11): antes un punto de color
// con texto al lado; "Registrada", "En auditoria" y "Subsanada" se
// veian con el mismo punto ambar, indistinguibles entre si. Ahora una
// pildora con fondo tenue y texto del color fuerte, una por cada una
// de las cinco categorias de mapa_estados.ts -- ya no solo tres.
export function EtiquetaEstado({ estado }: Propiedades) {
  const definicion = resolver_estado(estado);
  return (
    <span className={`${estilos.etiqueta} ${estilos[definicion.color]}`}>{definicion.texto}</span>
  );
}
