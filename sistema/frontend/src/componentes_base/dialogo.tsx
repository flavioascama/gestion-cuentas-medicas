import type { ReactNode } from "react";
import estilos from "./dialogo.module.css";

interface Propiedades {
  titulo: string;
  children: ReactNode;
  acciones: ReactNode;
  al_cerrar: () => void;
  ancho?: "normal" | "grande";
}

export function Dialogo({ titulo, children, acciones, al_cerrar, ancho = "normal" }: Propiedades) {
  const clase_caja = [estilos.caja, ancho === "grande" ? estilos.grande : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div
      className={estilos.fondo}
      role="presentation"
      onClick={(evento) => {
        if (evento.target === evento.currentTarget) al_cerrar();
      }}
    >
      <div className={clase_caja} role="dialog" aria-modal="true" aria-label={titulo}>
        <div className={estilos.titulo}>{titulo}</div>
        <div className={estilos.contenido}>{children}</div>
        <div className={estilos.acciones}>{acciones}</div>
      </div>
    </div>
  );
}
