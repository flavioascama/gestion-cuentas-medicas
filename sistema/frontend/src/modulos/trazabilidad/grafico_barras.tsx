import type { ColorEstado } from "../../componentes_base/mapa_estados";
import estilos from "./grafico_barras.module.css";

export type TonoGrafico = ColorEstado | "primario";

export interface FilaGrafico {
  clave: string;
  etiqueta: string;
  valor: number;
  tono: TonoGrafico;
  detalle?: string;
}

interface Propiedades {
  filas: FilaGrafico[];
  formatear_valor: (valor: number) => string;
  mensaje_vacio: string;
  // `seleccionada` presente (aunque sea null) = el grafico funciona como
  // filtro: la fila elegida conserva su color y las demas se atenuan.
  seleccionada?: string | null;
  al_pulsar?: (fila: FilaGrafico) => void;
  describir_accion?: (fila: FilaGrafico) => string;
}

function clase_relleno(fila: FilaGrafico, seleccionada: string | null | undefined): string {
  const atenuada =
    seleccionada !== undefined && seleccionada !== null && seleccionada !== fila.clave;
  return `${estilos.relleno} ${atenuada ? estilos.tono_atenuado : estilos[`tono_${fila.tono}`]}`;
}

function ContenidoFila({
  fila,
  ancho,
  formatear_valor,
  clase,
}: {
  fila: FilaGrafico;
  ancho: number;
  formatear_valor: (valor: number) => string;
  clase: string;
}) {
  return (
    <>
      <span className={estilos.etiqueta}>{fila.etiqueta}</span>
      <span className={estilos.pista}>
        <span className={clase} style={{ width: `${ancho}%` }} />
      </span>
      <span className={estilos.valor}>
        <span className={estilos.valor_numero}>{formatear_valor(fila.valor)}</span>
        {fila.detalle ? <span className={estilos.detalle}>{fila.detalle}</span> : null}
      </span>
    </>
  );
}

export function GraficoBarras({
  filas,
  formatear_valor,
  mensaje_vacio,
  seleccionada,
  al_pulsar,
  describir_accion,
}: Propiedades) {
  if (filas.length === 0) return <p className={estilos.vacio}>{mensaje_vacio}</p>;
  const valor_maximo = Math.max(...filas.map((fila) => fila.valor), Number.EPSILON);

  return (
    <div className={estilos.grafico}>
      {filas.map((fila) => {
        const contenido = (
          <ContenidoFila
            fila={fila}
            ancho={(fila.valor / valor_maximo) * 100}
            formatear_valor={formatear_valor}
            clase={clase_relleno(fila, seleccionada)}
          />
        );
        if (!al_pulsar) {
          return (
            <div key={fila.clave} className={estilos.fila}>
              {contenido}
            </div>
          );
        }
        return (
          <button
            key={fila.clave}
            type="button"
            className={`${estilos.fila} ${estilos.fila_pulsable}`}
            onClick={() => al_pulsar(fila)}
            aria-pressed={seleccionada === undefined ? undefined : seleccionada === fila.clave}
            aria-label={describir_accion?.(fila)}
          >
            {contenido}
          </button>
        );
      })}
    </div>
  );
}
