import type { IndicadoresCiclo } from "../../api/trazabilidad";
import { formatear_monto } from "../../utilidades/formato";
import { etiqueta_periodo, formatear_entero, formatear_porcentaje } from "./formato_indicadores";
import tonos from "./tonos_grafico.module.css";
import estilos from "./tarjetas_kpi.module.css";

interface Medidor {
  fraccion: number;
  tono: "alerta" | "critico";
}

interface Kpi {
  clave: string;
  etiqueta: string;
  valor: string;
  contexto: string;
  medidor?: Medidor;
}

function de_cuantos(fraccion: number, total: number, unidad: string): string {
  return `${formatear_entero(Math.round(fraccion * total))} de ${formatear_entero(total)} ${unidad}`;
}

function construir_kpis(indicadores: IndicadoresCiclo, periodo: string): Kpi[] {
  const alcance = periodo ? etiqueta_periodo(periodo) : "Todos los periodos";
  const lotes = indicadores.lotes_evaluados;
  const cuentas = indicadores.cuentas_evaluadas;
  return [
    {
      clave: "cuentas",
      etiqueta: "Cuentas evaluadas",
      valor: formatear_entero(cuentas),
      contexto: alcance,
    },
    {
      clave: "lotes",
      etiqueta: "Lotes evaluados",
      valor: formatear_entero(lotes),
      contexto: alcance,
    },
    {
      clave: "observados",
      etiqueta: "Lotes observados",
      valor: formatear_porcentaje(indicadores.pct_lotes_observados),
      contexto: de_cuantos(indicadores.pct_lotes_observados, lotes, "lotes"),
      medidor: { fraccion: indicadores.pct_lotes_observados, tono: "alerta" },
    },
    {
      clave: "rechazados",
      etiqueta: "Lotes rechazados",
      valor: formatear_porcentaje(indicadores.pct_lotes_rechazados),
      contexto: de_cuantos(indicadores.pct_lotes_rechazados, lotes, "lotes"),
      medidor: { fraccion: indicadores.pct_lotes_rechazados, tono: "critico" },
    },
    {
      clave: "glosas",
      etiqueta: "Tasa de glosas",
      valor: formatear_porcentaje(indicadores.tasa_glosas),
      contexto: de_cuantos(indicadores.tasa_glosas, cuentas, "cuentas"),
      medidor: { fraccion: indicadores.tasa_glosas, tono: "alerta" },
    },
    {
      clave: "cartera",
      etiqueta: "Cartera por cobrar",
      valor: formatear_monto(indicadores.cartera_por_cobrar),
      contexto: "Saldo no pagado de liquidaciones",
    },
  ];
}

// El medidor solo acompana al porcentaje ya escrito en la tarjeta (por
// eso queda oculto para lectores de pantalla); la pista es el paso
// suave del mismo color, no un gris.
function BarraMedidor({ medidor }: { medidor: Medidor }) {
  const ancho = Math.min(Math.max(medidor.fraccion, 0), 1) * 100;
  return (
    <span className={`${estilos.medidor} ${estilos[`pista_${medidor.tono}`]}`} aria-hidden="true">
      <span
        className={`${estilos.relleno_medidor} ${tonos[`fondo_${medidor.tono}`]}`}
        style={{ width: `${ancho}%` }}
      />
    </span>
  );
}

export function FilaKpi({
  indicadores,
  periodo,
}: {
  indicadores: IndicadoresCiclo;
  periodo: string;
}) {
  return (
    <div className={estilos.fila}>
      {construir_kpis(indicadores, periodo).map((kpi) => (
        <div key={kpi.clave} className={estilos.kpi}>
          <span className={estilos.etiqueta}>{kpi.etiqueta}</span>
          <span className={estilos.valor}>{kpi.valor}</span>
          <span className={estilos.contexto}>{kpi.contexto}</span>
          {kpi.medidor ? <BarraMedidor medidor={kpi.medidor} /> : null}
        </div>
      ))}
    </div>
  );
}
