import { useState } from "react";
import type { IndicadoresCiclo, IndicadoresIafas, TiempoEtapa } from "../../api/trazabilidad";
import { ControlSegmentado, type OpcionSegmento } from "../../componentes_base/control_segmentado";
import { resolver_estado } from "../../componentes_base/mapa_estados";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_monto } from "../../utilidades/formato";
import type { FiltrosPanel } from "./barra_filtros";
import {
  METRICAS_IAFAS,
  SERIES_LOTE,
  construir_columnas_periodo,
  construir_filas_estados,
  construir_filas_etapas,
  construir_filas_iafas,
  type MetricaIafas,
} from "./datos_indicadores";
import {
  etiqueta_periodo,
  formatear_entero,
  formatear_horas,
  formatear_porcentaje,
} from "./formato_indicadores";
import type { ColumnaApilada } from "./geometria_columnas";
import { GraficoBarras, type FilaGrafico } from "./grafico_barras";
import { GraficoColumnasApiladas } from "./grafico_columnas_apiladas";
import { TarjetaGrafico } from "./tarjeta_grafico";
import estilos from "./graficos_panel.module.css";

interface PropiedadesGraficos {
  indicadores: IndicadoresCiclo;
  filtros: FiltrosPanel;
  al_alternar_periodo: (periodo: string) => void;
  al_alternar_iafas: (codigo: string) => void;
  al_ver_cuentas: (estado: string) => void;
}

interface FilaEvolucion {
  clave: string;
  periodo: string;
  aceptado: number;
  en_tramite: number;
  observado: number;
  rechazado: number;
  total: number;
}

function filas_evolucion(columnas: ColumnaApilada[]): FilaEvolucion[] {
  return columnas.map((columna) => {
    const valor = (clave: string) => columna.valores[clave] ?? 0;
    return {
      clave: columna.clave,
      periodo: columna.etiqueta,
      aceptado: valor("aceptado"),
      en_tramite: valor("en_tramite"),
      observado: valor("observado"),
      rechazado: valor("rechazado"),
      total: SERIES_LOTE.reduce((suma, serie) => suma + valor(serie.clave), 0),
    };
  });
}

const _COLUMNAS_EVOLUCION: ColumnaTabla<FilaEvolucion>[] = [
  { clave: "periodo", encabezado: "Periodo" },
  ...SERIES_LOTE.map((serie) => ({
    clave: serie.clave as keyof FilaEvolucion,
    encabezado: serie.etiqueta,
    alinear_derecha: true,
  })),
  { clave: "total", encabezado: "Total", alinear_derecha: true },
];

function TarjetaEvolucion({ indicadores, filtros, al_alternar_periodo }: PropiedadesGraficos) {
  const columnas = construir_columnas_periodo(indicadores.lotes_por_periodo);
  return (
    <TarjetaGrafico
      titulo="Evolución de lotes por periodo"
      subtitulo="Resultado de los lotes de cada periodo"
      tabla={
        <TablaDatos
          columnas={_COLUMNAS_EVOLUCION}
          filas={filas_evolucion(columnas)}
          obtener_clave={(fila) => fila.clave}
          mensaje_vacio="No hay lotes registrados."
          al_hacer_clic_fila={(fila) => al_alternar_periodo(fila.clave)}
        />
      }
    >
      <GraficoColumnasApiladas
        series={SERIES_LOTE}
        columnas={columnas}
        seleccionada={filtros.periodo || null}
        al_pulsar={al_alternar_periodo}
        unidad={{ singular: "lote", plural: "lotes" }}
        texto_accion={
          filtros.periodo
            ? "Pulse para cambiar o quitar el filtro de periodo."
            : "Pulse para filtrar el panel por este periodo."
        }
        mensaje_vacio="No hay lotes registrados para la IAFAS elegida."
      />
    </TarjetaGrafico>
  );
}

const _COLUMNAS_IAFAS: ColumnaTabla<IndicadoresIafas>[] = [
  { clave: "iafas_razon_social", encabezado: "IAFAS" },
  { clave: "cuentas", encabezado: "Cuentas", alinear_derecha: true },
  {
    clave: "monto_registrado",
    encabezado: "Monto registrado",
    alinear_derecha: true,
    formatear: (fila) => formatear_monto(fila.monto_registrado),
  },
  {
    clave: "cartera_por_cobrar",
    encabezado: "Cartera",
    alinear_derecha: true,
    formatear: (fila) => formatear_monto(fila.cartera_por_cobrar),
  },
  {
    clave: "tasa_glosas",
    encabezado: "Glosas",
    alinear_derecha: true,
    formatear: (fila) => formatear_porcentaje(fila.tasa_glosas),
  },
  { clave: "lotes", encabezado: "Lotes", alinear_derecha: true },
  {
    clave: "pct_lotes_observados",
    encabezado: "Observados",
    alinear_derecha: true,
    formatear: (fila) => formatear_porcentaje(fila.pct_lotes_observados),
  },
];

const _OPCIONES_METRICA: OpcionSegmento<MetricaIafas>[] = (
  Object.keys(METRICAS_IAFAS) as MetricaIafas[]
).map((valor) => ({ valor, etiqueta: METRICAS_IAFAS[valor].etiqueta }));

function TarjetaComparativoIafas({ indicadores, filtros, al_alternar_iafas }: PropiedadesGraficos) {
  const [metrica, set_metrica] = useState<MetricaIafas>("cuentas");
  const definicion = METRICAS_IAFAS[metrica];
  const alcance = filtros.periodo ? etiqueta_periodo(filtros.periodo) : "Todos los periodos";
  return (
    <TarjetaGrafico
      titulo="Comparativo por IAFAS"
      subtitulo={alcance}
      controles={
        <ControlSegmentado
          opciones={_OPCIONES_METRICA}
          valor={metrica}
          al_cambiar={set_metrica}
          etiqueta_accesible="Indicador a comparar"
        />
      }
      tabla={
        <TablaDatos
          columnas={_COLUMNAS_IAFAS}
          filas={indicadores.por_iafas}
          obtener_clave={(fila) => fila.iafas_codigo}
          mensaje_vacio="No hay IAFAS registradas."
          al_hacer_clic_fila={(fila) => al_alternar_iafas(fila.iafas_codigo)}
        />
      }
    >
      <GraficoBarras
        filas={construir_filas_iafas(indicadores.por_iafas, metrica)}
        formatear_valor={definicion.formatear}
        mensaje_vacio="No hay IAFAS registradas."
        seleccionada={filtros.iafas_codigo || null}
        al_pulsar={(fila) => al_alternar_iafas(fila.clave)}
        describir_accion={(fila) =>
          `${fila.etiqueta}: ${definicion.formatear(fila.valor)}. Pulse para filtrar el panel por esta IAFAS.`
        }
      />
    </TarjetaGrafico>
  );
}

const _COLUMNAS_ESTADOS: ColumnaTabla<FilaGrafico>[] = [
  { clave: "etiqueta", encabezado: "Estado" },
  {
    clave: "valor",
    encabezado: "Cuentas",
    alinear_derecha: true,
    formatear: (fila) => formatear_entero(fila.valor),
  },
  { clave: "detalle", encabezado: "Del total", alinear_derecha: true },
];

function TarjetaEstados({ indicadores, filtros, al_ver_cuentas }: PropiedadesGraficos) {
  const filas = construir_filas_estados(indicadores.distribucion_por_estado);
  // La bandeja de Cuentas filtra por fecha exacta, no por mes: se avisa
  // en vez de mostrar una cantidad distinta sin explicacion.
  const nota = filtros.periodo ? etiqueta_periodo(filtros.periodo) : "Todos los periodos";
  return (
    <TarjetaGrafico
      titulo="Distribución de cuentas por estado"
      subtitulo={nota}
      tabla={
        <TablaDatos
          columnas={_COLUMNAS_ESTADOS}
          filas={filas}
          obtener_clave={(fila) => fila.clave}
          mensaje_vacio="No hay cuentas para los filtros seleccionados."
          al_hacer_clic_fila={(fila) => al_ver_cuentas(fila.clave)}
        />
      }
    >
      <GraficoBarras
        filas={filas}
        formatear_valor={formatear_entero}
        mensaje_vacio="No hay cuentas para los filtros seleccionados."
        al_pulsar={(fila) => al_ver_cuentas(fila.clave)}
        describir_accion={(fila) =>
          `${fila.etiqueta}: ${formatear_entero(fila.valor)} cuentas. Pulse para verlas en la bandeja.`
        }
      />
    </TarjetaGrafico>
  );
}

const _COLUMNAS_ETAPAS: ColumnaTabla<TiempoEtapa>[] = [
  { clave: "etapa", encabezado: "Etapa", formatear: (fila) => resolver_estado(fila.etapa).texto },
  {
    clave: "promedio_horas",
    encabezado: "Tiempo promedio",
    alinear_derecha: true,
    formatear: (fila) => formatear_horas(fila.promedio_horas),
  },
  {
    clave: "transiciones",
    encabezado: "Transiciones",
    alinear_derecha: true,
    formatear: (fila) => formatear_entero(fila.transiciones),
  },
];

function TarjetaEtapas({ indicadores }: PropiedadesGraficos) {
  const ordenadas = [...indicadores.tiempo_por_etapa].sort(
    (a, b) => b.promedio_horas - a.promedio_horas,
  );
  return (
    <TarjetaGrafico
      titulo="Tiempo de ciclo por etapa"
      subtitulo="Tiempo promedio para llegar a cada estado. En ámbar, la etapa más lenta."
      tabla={
        <TablaDatos
          columnas={_COLUMNAS_ETAPAS}
          filas={ordenadas}
          obtener_clave={(fila) => fila.etapa}
          mensaje_vacio="No hay transiciones registradas para los filtros seleccionados."
        />
      }
    >
      <GraficoBarras
        filas={construir_filas_etapas(indicadores.tiempo_por_etapa)}
        formatear_valor={formatear_horas}
        mensaje_vacio="No hay transiciones registradas para los filtros seleccionados."
      />
    </TarjetaGrafico>
  );
}

export function GraficosPanel(propiedades: PropiedadesGraficos) {
  return (
    <div className={estilos.cuadricula}>
      <TarjetaEvolucion {...propiedades} />
      <TarjetaComparativoIafas {...propiedades} />
      <TarjetaEstados {...propiedades} />
      <TarjetaEtapas {...propiedades} />
    </div>
  );
}
