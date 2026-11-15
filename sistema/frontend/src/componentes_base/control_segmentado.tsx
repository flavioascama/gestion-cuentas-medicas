import estilos from "./control_segmentado.module.css";

export interface OpcionSegmento<T extends string> {
  valor: T;
  etiqueta: string;
}

interface Propiedades<T extends string> {
  opciones: OpcionSegmento<T>[];
  valor: T;
  al_cambiar: (valor: T) => void;
  etiqueta_accesible: string;
}

// Grupo de botones excluyentes (una sola opcion activa): para alternar
// entre vistas o metricas de un mismo grafico sin abrir un desplegable.
export function ControlSegmentado<T extends string>({
  opciones,
  valor,
  al_cambiar,
  etiqueta_accesible,
}: Propiedades<T>) {
  return (
    <div className={estilos.grupo} role="group" aria-label={etiqueta_accesible}>
      {opciones.map((opcion) => (
        <button
          key={opcion.valor}
          type="button"
          className={`${estilos.opcion} ${opcion.valor === valor ? estilos.opcion_activa : ""}`}
          aria-pressed={opcion.valor === valor}
          onClick={() => al_cambiar(opcion.valor)}
        >
          {opcion.etiqueta}
        </button>
      ))}
    </div>
  );
}
