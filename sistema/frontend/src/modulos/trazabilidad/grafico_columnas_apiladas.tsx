import { useState, type KeyboardEvent } from "react";
import { formatear_entero } from "./formato_indicadores";
import {
  ALTO_GRAFICO,
  ANCHO_COLUMNA,
  MARGEN,
  calcular_geometria,
  trazo_tapa,
  type ColumnaApilada,
  type Escala,
  type GeometriaColumna,
  type SerieApilada,
} from "./geometria_columnas";
import { TooltipGrafico, type FilaTooltip } from "./tooltip_grafico";
import { usar_ancho } from "./usar_ancho";
import tonos from "./tonos_grafico.module.css";
import estilos from "./grafico_columnas_apiladas.module.css";

export interface Unidad {
  singular: string;
  plural: string;
}

interface Propiedades {
  series: SerieApilada[];
  columnas: ColumnaApilada[];
  seleccionada: string | null;
  al_pulsar: (clave: string) => void;
  unidad: Unidad;
  texto_accion: string;
  mensaje_vacio: string;
}

function LeyendaSeries({
  series,
  ocultas,
  al_alternar,
}: {
  series: SerieApilada[];
  ocultas: Set<string>;
  al_alternar: (clave: string) => void;
}) {
  return (
    <div className={estilos.leyenda} role="group" aria-label="Mostrar u ocultar categorías">
      {series.map((serie) => {
        const visible = !ocultas.has(serie.clave);
        return (
          <button
            key={serie.clave}
            type="button"
            className={`${estilos.item_leyenda} ${visible ? "" : estilos.item_oculto}`}
            aria-pressed={visible}
            onClick={() => al_alternar(serie.clave)}
          >
            <span className={`${estilos.muestra} ${tonos[`fondo_${serie.tono}`]}`} />
            {serie.etiqueta}
          </button>
        );
      })}
    </div>
  );
}

function EjeY({ escala, ancho }: { escala: Escala; ancho: number }) {
  const marcas: number[] = [];
  for (let valor = 0; valor <= escala.tope; valor += escala.paso) marcas.push(valor);
  const base = MARGEN.arriba + escala.alto_trazado;
  return (
    <g aria-hidden="true">
      {marcas.map((valor) => {
        const y = base - (valor / escala.tope) * escala.alto_trazado;
        return (
          <g key={valor}>
            <line
              className={estilos.rejilla}
              x1={MARGEN.izquierda}
              x2={ancho - MARGEN.derecha}
              y1={y}
              y2={y}
            />
            <text
              className={estilos.etiqueta_eje}
              x={MARGEN.izquierda - 8}
              y={y + 4}
              textAnchor="end"
            >
              {formatear_entero(valor)}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function SegmentosColumna({ geometria }: { geometria: GeometriaColumna }) {
  const x = geometria.x_centro - ANCHO_COLUMNA / 2;
  return (
    <>
      {geometria.segmentos.map((segmento) =>
        segmento.es_tapa ? (
          <path
            key={segmento.serie.clave}
            className={tonos[`relleno_${segmento.serie.tono}`]}
            d={trazo_tapa(x, segmento.y, ANCHO_COLUMNA, segmento.alto)}
          />
        ) : (
          <rect
            key={segmento.serie.clave}
            className={tonos[`relleno_${segmento.serie.tono}`]}
            x={x}
            y={segmento.y}
            width={ANCHO_COLUMNA}
            height={segmento.alto}
          />
        ),
      )}
    </>
  );
}

interface PropiedadesColumna {
  geometria: GeometriaColumna;
  banda: number;
  escala: Escala;
  estado: "normal" | "activa" | "atenuada";
  seleccionada: boolean;
  etiqueta_accesible: string;
  al_activar: (clave: string | null) => void;
  al_pulsar: (clave: string) => void;
}

function ColumnaSvg(propiedades: PropiedadesColumna) {
  const { geometria, banda, escala, estado, seleccionada, al_activar, al_pulsar } = propiedades;
  const clave = geometria.columna.clave;
  const al_tecla = (evento: KeyboardEvent<SVGRectElement>) => {
    if (evento.key !== "Enter" && evento.key !== " ") return;
    evento.preventDefault();
    al_pulsar(clave);
  };
  return (
    <g className={estilos[`columna_${estado}`]}>
      <SegmentosColumna geometria={geometria} />
      {geometria.total > 0 ? (
        <text
          className={estilos.etiqueta_tapa}
          x={geometria.x_centro}
          y={geometria.y_tope - 6}
          textAnchor="middle"
        >
          {formatear_entero(geometria.total)}
        </text>
      ) : null}
      <text
        className={estilos.etiqueta_eje}
        x={geometria.x_centro}
        y={ALTO_GRAFICO - 8}
        textAnchor="middle"
      >
        {geometria.columna.etiqueta_eje ?? geometria.columna.etiqueta}
      </text>
      <rect
        className={estilos.objetivo}
        x={geometria.x_centro - banda / 2}
        y={MARGEN.arriba}
        width={banda}
        height={escala.alto_trazado + MARGEN.abajo}
        tabIndex={0}
        role="button"
        aria-pressed={seleccionada}
        aria-label={propiedades.etiqueta_accesible}
        onPointerEnter={() => al_activar(clave)}
        onPointerLeave={() => al_activar(null)}
        onFocus={() => al_activar(clave)}
        onBlur={() => al_activar(null)}
        onClick={() => al_pulsar(clave)}
        onKeyDown={al_tecla}
      />
    </g>
  );
}

function filas_tooltip(
  geometria: GeometriaColumna,
  visibles: SerieApilada[],
  unidad: Unidad,
): FilaTooltip[] {
  const filas: FilaTooltip[] = visibles.map((serie) => ({
    clave: serie.clave,
    etiqueta: serie.etiqueta,
    valor: formatear_entero(geometria.columna.valores[serie.clave] ?? 0),
    clase_clave: tonos[`fondo_${serie.tono}`],
  }));
  return [
    ...filas,
    {
      clave: "total",
      etiqueta: `Total de ${unidad.plural}`,
      valor: formatear_entero(geometria.total),
    },
  ];
}

function describir_columna(
  geometria: GeometriaColumna,
  visibles: SerieApilada[],
  unidad: Unidad,
): string {
  const partes = visibles.map(
    (serie) => `${serie.etiqueta} ${geometria.columna.valores[serie.clave] ?? 0}`,
  );
  const nombre = geometria.total === 1 ? unidad.singular : unidad.plural;
  return `${geometria.columna.etiqueta}: ${geometria.total} ${nombre} (${partes.join(", ")}).`;
}

function alternar_en_conjunto(previas: Set<string>, clave: string): Set<string> {
  const nuevas = new Set(previas);
  if (nuevas.has(clave)) nuevas.delete(clave);
  else nuevas.add(clave);
  return nuevas;
}

function estado_columna(
  clave: string,
  activa: string | null,
  seleccionada: string | null,
): PropiedadesColumna["estado"] {
  if (clave === activa) return "activa";
  if (seleccionada !== null && clave !== seleccionada) return "atenuada";
  return "normal";
}

export function GraficoColumnasApiladas(propiedades: Propiedades) {
  const { series, columnas, seleccionada, al_pulsar, unidad } = propiedades;
  const { referencia, ancho } = usar_ancho<HTMLDivElement>();
  const [ocultas, set_ocultas] = useState<Set<string>>(() => new Set());
  const [activa, set_activa] = useState<string | null>(null);

  const visibles = series.filter((serie) => !ocultas.has(serie.clave));
  const { escala, banda, geometria } = calcular_geometria(columnas, visibles, ancho);
  const columna_activa = geometria.find((g) => g.columna.clave === activa);
  const seleccion_valida = geometria.some((g) => g.columna.clave === seleccionada)
    ? seleccionada
    : null;

  const alternar_serie = (clave: string) =>
    set_ocultas((previas) => alternar_en_conjunto(previas, clave));

  if (columnas.length === 0) return <p className={estilos.vacio}>{propiedades.mensaje_vacio}</p>;

  return (
    <div>
      <LeyendaSeries series={series} ocultas={ocultas} al_alternar={alternar_serie} />
      <div ref={referencia} className={estilos.lienzo}>
        {ancho > 0 ? (
          <svg width={ancho} height={ALTO_GRAFICO} className={estilos.svg}>
            <EjeY escala={escala} ancho={ancho} />
            {geometria.map((g) => (
              <ColumnaSvg
                key={g.columna.clave}
                geometria={g}
                banda={banda}
                escala={escala}
                estado={estado_columna(g.columna.clave, activa, seleccion_valida)}
                seleccionada={g.columna.clave === seleccion_valida}
                etiqueta_accesible={`${describir_columna(g, visibles, unidad)} ${propiedades.texto_accion}`}
                al_activar={set_activa}
                al_pulsar={al_pulsar}
              />
            ))}
          </svg>
        ) : null}
        {columna_activa ? (
          <TooltipGrafico
            titulo={columna_activa.columna.etiqueta}
            filas={filas_tooltip(columna_activa, visibles, unidad)}
            x={Math.min(Math.max(columna_activa.x_centro, 90), Math.max(ancho - 90, 90))}
            y={columna_activa.y_tope - 12}
          />
        ) : null}
      </div>
    </div>
  );
}
