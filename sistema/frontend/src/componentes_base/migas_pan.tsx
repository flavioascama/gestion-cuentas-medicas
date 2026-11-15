import { Link } from "react-router-dom";
import estilos from "./migas_pan.module.css";

export interface MigaPan {
  etiqueta: string;
  ruta?: string;
}

interface Propiedades {
  migas: MigaPan[];
}

export function MigasPan({ migas }: Propiedades) {
  return (
    <nav className={estilos.migas} aria-label="Ruta de navegación">
      {migas.map((miga, indice) => (
        <span key={miga.etiqueta}>
          {miga.ruta ? <Link to={miga.ruta}>{miga.etiqueta}</Link> : miga.etiqueta}
          {indice < migas.length - 1 ? " / " : null}
        </span>
      ))}
    </nav>
  );
}
