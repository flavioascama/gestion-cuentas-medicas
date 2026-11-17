import { useQuery } from "@tanstack/react-query";
import { listar_iafas, type ResumenIafas } from "../../api/iafas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Selector } from "../../componentes_base/selector";
import {
  OPCIONES_ESTADO_LOTE,
  formatear_periodo_legible,
  hay_filtros_aplicados,
  periodo_desde_mes_input,
  type Filtros,
} from "./filtros_lotes";
import estilos from "./bandeja_lotes.module.css";

function construir_opciones_iafas(iafas: ResumenIafas[]): { valor: string; etiqueta: string }[] {
  return [
    { valor: "", etiqueta: "Todas" },
    ...iafas.map((i) => ({ valor: String(i.id), etiqueta: `${i.codigo} — ${i.razon_social}` })),
  ];
}

interface PropiedadesFiltro {
  filtros: Filtros;
  al_cambiar: (filtros: Filtros) => void;
}

function FiltroPeriodo({ filtros, al_cambiar }: PropiedadesFiltro) {
  return (
    <div className={estilos.filtro}>
      <CampoTexto
        etiqueta="Periodo"
        type="month"
        placeholder="Todos los periodos"
        value={formatear_periodo_legible(filtros.periodo)}
        onChange={(evento) =>
          al_cambiar({ ...filtros, periodo: periodo_desde_mes_input(evento.target.value) })
        }
      />
    </div>
  );
}

function FiltroIafas({ filtros, al_cambiar }: PropiedadesFiltro) {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  return (
    <div className={estilos.filtro}>
      <Selector
        etiqueta="IAFAS"
        opciones={construir_opciones_iafas(consulta_iafas.data ?? [])}
        value={filtros.iafas_id}
        onChange={(evento) => al_cambiar({ ...filtros, iafas_id: evento.target.value })}
      />
    </div>
  );
}

interface Propiedades extends PropiedadesFiltro {
  busqueda: string;
  al_cambiar_busqueda: (busqueda: string) => void;
  al_limpiar: () => void;
}

export function FiltrosBandejaLotes({
  filtros,
  al_cambiar,
  busqueda,
  al_cambiar_busqueda,
  al_limpiar,
}: Propiedades) {
  return (
    <div className={estilos.filtros}>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => al_cambiar_busqueda(evento.target.value)}
          placeholder="N.° de lote"
        />
      </div>
      <FiltroPeriodo filtros={filtros} al_cambiar={al_cambiar} />
      <div className={estilos.filtro}>
        <Selector
          etiqueta="Estado"
          opciones={OPCIONES_ESTADO_LOTE}
          value={filtros.estado}
          onChange={(evento) => al_cambiar({ ...filtros, estado: evento.target.value })}
        />
      </div>
      <FiltroIafas filtros={filtros} al_cambiar={al_cambiar} />
      <div className={estilos.limpiar_filtros}>
        <Boton
          variante="terciario"
          onClick={al_limpiar}
          disabled={!hay_filtros_aplicados(filtros, busqueda)}
        >
          Limpiar filtros
        </Boton>
      </div>
    </div>
  );
}
