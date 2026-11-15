// Calculo puro (sin React) de las columnas apiladas: escala del eje,
// posicion de cada columna y de cada segmento. Separado del componente
// para que la aritmetica se lea sola y el componente solo dibuje.

export type TonoSerie = "exito" | "proceso" | "alerta" | "critico";

export interface SerieApilada {
  clave: string;
  etiqueta: string;
  tono: TonoSerie;
}

export interface ColumnaApilada {
  clave: string;
  etiqueta: string;
  valores: Record<string, number>;
}

export const ALTO_GRAFICO = 260;
export const MARGEN = { arriba: 24, derecha: 8, abajo: 28, izquierda: 44 };
// Marcas finas (<= 24 px) con el resto de la banda como aire, extremo
// de dato redondeado de 4 px y 2 px de superficie entre segmentos.
export const ANCHO_COLUMNA = 24;
const _HUECO = 2;
const _RADIO = 4;

export interface Escala {
  tope: number;
  paso: number;
  alto_trazado: number;
}

export interface Segmento {
  serie: SerieApilada;
  valor: number;
  y: number;
  alto: number;
  es_tapa: boolean;
}

export interface GeometriaColumna {
  columna: ColumnaApilada;
  x_centro: number;
  total: number;
  y_tope: number;
  segmentos: Segmento[];
}

// Paso "limpio" (1, 2 o 5 por potencia de 10) para unas cuatro marcas
// del eje; nunca menor que 1, porque se cuentan lotes enteros.
export function calcular_escala(maximo: number): Escala {
  const referencia = Math.max(maximo, 1);
  const bruto = referencia / 4;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const relativo = bruto / potencia;
  const factor = relativo <= 1 ? 1 : relativo <= 2 ? 2 : relativo <= 5 ? 5 : 10;
  const paso = Math.max(1, factor * potencia);
  return {
    paso,
    tope: Math.ceil(referencia / paso) * paso,
    alto_trazado: ALTO_GRAFICO - MARGEN.arriba - MARGEN.abajo,
  };
}

function calcular_segmentos(
  columna: ColumnaApilada,
  visibles: SerieApilada[],
  escala: Escala,
): Segmento[] {
  const base = MARGEN.arriba + escala.alto_trazado;
  const con_valor = visibles.filter((serie) => (columna.valores[serie.clave] ?? 0) > 0);
  let acumulado = 0;
  return con_valor.map((serie, indice) => {
    const valor = columna.valores[serie.clave] ?? 0;
    const y_inferior = base - (acumulado / escala.tope) * escala.alto_trazado;
    acumulado += valor;
    const y_superior = base - (acumulado / escala.tope) * escala.alto_trazado;
    const hueco = indice === 0 ? 0 : _HUECO;
    return {
      serie,
      valor,
      y: y_superior,
      alto: Math.max(y_inferior - hueco - y_superior, 0.5),
      es_tapa: indice === con_valor.length - 1,
    };
  });
}

export function total_visible(columna: ColumnaApilada, visibles: SerieApilada[]): number {
  return visibles.reduce((suma, serie) => suma + (columna.valores[serie.clave] ?? 0), 0);
}

export function calcular_geometria(
  columnas: ColumnaApilada[],
  visibles: SerieApilada[],
  ancho: number,
): { escala: Escala; banda: number; geometria: GeometriaColumna[] } {
  const totales = columnas.map((columna) => total_visible(columna, visibles));
  const escala = calcular_escala(Math.max(...totales, 0));
  const ancho_trazado = Math.max(ancho - MARGEN.izquierda - MARGEN.derecha, 0);
  const banda = columnas.length > 0 ? ancho_trazado / columnas.length : 0;
  const base = MARGEN.arriba + escala.alto_trazado;
  const geometria = columnas.map((columna, indice) => {
    const total = totales[indice] ?? 0;
    return {
      columna,
      x_centro: MARGEN.izquierda + banda * (indice + 0.5),
      total,
      y_tope: base - (total / escala.tope) * escala.alto_trazado,
      segmentos: calcular_segmentos(columna, visibles, escala),
    };
  });
  return { escala, banda, geometria };
}

// Solo el segmento superior lleva el extremo redondeado; la base de la
// columna queda recta sobre el eje.
export function trazo_tapa(x: number, y: number, ancho: number, alto: number): string {
  const r = Math.min(_RADIO, alto, ancho / 2);
  return [
    `M${x},${y + alto}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + ancho - r}`,
    `Q${x + ancho},${y} ${x + ancho},${y + r}`,
    `V${y + alto}`,
    "Z",
  ].join(" ");
}
