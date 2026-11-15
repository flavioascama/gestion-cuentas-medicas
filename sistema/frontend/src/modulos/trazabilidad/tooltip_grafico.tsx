import estilos from "./tooltip_grafico.module.css";

export interface FilaTooltip {
  clave: string;
  etiqueta: string;
  valor: string;
  clase_clave?: string;
}

interface Propiedades {
  titulo: string;
  filas: FilaTooltip[];
  x: number;
  y: number;
}

// Solo refuerza lo que el grafico ya muestra: la etiqueta accesible de
// cada marca y la vista de tabla llevan los mismos valores, por eso la
// ayuda emergente queda oculta para los lectores de pantalla.
export function TooltipGrafico({ titulo, filas, x, y }: Propiedades) {
  return (
    <div className={estilos.tooltip} style={{ left: x, top: y }} aria-hidden="true">
      <div className={estilos.titulo}>{titulo}</div>
      {filas.map((fila) => (
        <div key={fila.clave} className={estilos.fila}>
          {fila.clase_clave ? (
            <span className={`${estilos.clave} ${fila.clase_clave}`} />
          ) : (
            <span className={estilos.clave_vacia} />
          )}
          <span className={estilos.valor}>{fila.valor}</span>
          <span className={estilos.etiqueta}>{fila.etiqueta}</span>
        </div>
      ))}
    </div>
  );
}
