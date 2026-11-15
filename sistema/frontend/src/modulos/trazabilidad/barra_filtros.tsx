import { useQuery } from "@tanstack/react-query";
import { listar_iafas, type ResumenIafas } from "../../api/iafas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Selector } from "../../componentes_base/selector";
import { mes_input_a_periodo, periodo_a_mes_input } from "./formato_indicadores";
import estilos from "./barra_filtros.module.css";

export interface FiltrosPanel {
  iafas_codigo: string;
  periodo: string;
}

function opciones_iafas(iafas: ResumenIafas[]): { valor: string; etiqueta: string }[] {
  return [
    { valor: "", etiqueta: "Todas" },
    ...iafas.map((i) => ({ valor: i.codigo, etiqueta: `${i.codigo} — ${i.razon_social}` })),
  ];
}

// Una sola fila de filtros encima de todo lo que filtra: cada tarjeta y
// cada grafico se recalculan sobre el mismo corte. Pulsar un periodo o
// una IAFAS en los graficos escribe aqui mismo.
export function BarraFiltros({
  filtros,
  al_cambiar,
}: {
  filtros: FiltrosPanel;
  al_cambiar: (filtros: FiltrosPanel) => void;
}) {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  const hay_filtros = filtros.iafas_codigo !== "" || filtros.periodo !== "";

  return (
    <div className={estilos.barra}>
      <div className={estilos.campos}>
        <div className={estilos.campo_iafas}>
          <Selector
            etiqueta="IAFAS"
            opciones={opciones_iafas(consulta_iafas.data ?? [])}
            value={filtros.iafas_codigo}
            onChange={(evento) => al_cambiar({ ...filtros, iafas_codigo: evento.target.value })}
          />
        </div>
        <div className={estilos.campo}>
          <CampoTexto
            etiqueta="Periodo"
            type="month"
            value={periodo_a_mes_input(filtros.periodo)}
            onChange={(evento) =>
              al_cambiar({ ...filtros, periodo: mes_input_a_periodo(evento.target.value) })
            }
          />
        </div>
        <div className={estilos.accion}>
          <span className={estilos.espaciador} aria-hidden="true">
            &nbsp;
          </span>
          <div className={estilos.fila_boton}>
            <Boton
              variante="terciario"
              onClick={() => al_cambiar({ iafas_codigo: "", periodo: "" })}
              disabled={!hay_filtros}
            >
              Limpiar filtros
            </Boton>
          </div>
        </div>
      </div>
    </div>
  );
}
