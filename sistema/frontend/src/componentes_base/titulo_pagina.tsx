import type { ReactNode } from "react";
import estilos from "./titulo_pagina.module.css";

interface Propiedades {
  titulo: string;
  acciones?: ReactNode;
}

export function TituloPagina({ titulo, acciones }: Propiedades) {
  return (
    <div className={estilos.contenedor}>
      <h1 className={estilos.titulo}>{titulo}</h1>
      {acciones ? <div className={estilos.acciones}>{acciones}</div> : null}
    </div>
  );
}
