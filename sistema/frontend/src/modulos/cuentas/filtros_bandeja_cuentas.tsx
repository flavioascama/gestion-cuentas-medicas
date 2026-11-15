import { useQuery } from "@tanstack/react-query";
import { listar_iafas, type ResumenIafas } from "../../api/iafas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { resolver_estado } from "../../componentes_base/mapa_estados";
import { Selector } from "../../componentes_base/selector";
import estilos from "./bandeja_cuentas.module.css";

// Las cuatro etapas del ciclo que describe la tesis (Seccion 5.2.1) mas
// las anuladas, en vez de los catorce estados de la Tabla 58 (2026-11-12):
// el estado exacto sigue en la pildora de cada fila. El panel gerencial
// puede abrir la bandeja filtrada por un estado exacto (?estado=); ese
// filtro se muestra como una etiqueta que se puede quitar.
const _OPCIONES_ETAPA = [
  { valor: "", etiqueta: "Todas" },
  { valor: "ADMISION", etiqueta: "Admisión" },
  { valor: "FACTURACION", etiqueta: "Facturación" },
  { valor: "AUDITORIA", etiqueta: "Auditoría y glosas" },
  { valor: "LIQUIDACION", etiqueta: "Liquidación y pago" },
  { valor: "ANULADA", etiqueta: "Anuladas" },
];

export interface FiltrosCuentas {
  etapa: string;
  estado: string;
  iafas_codigo: string;
  fecha: string;
}

interface Propiedades {
  filtros: FiltrosCuentas;
  al_cambiar: (filtros: FiltrosCuentas) => void;
  busqueda: string;
  al_cambiar_busqueda: (busqueda: string) => void;
  al_limpiar: () => void;
}

function construir_opciones_iafas(iafas: ResumenIafas[]): { valor: string; etiqueta: string }[] {
  return [
    { valor: "", etiqueta: "Todas" },
    ...iafas.map((i) => ({ valor: i.codigo, etiqueta: `${i.codigo} — ${i.razon_social}` })),
  ];
}

function hay_filtros_activos(filtros: FiltrosCuentas, busqueda: string): boolean {
  return (
    busqueda !== "" ||
    filtros.etapa !== "" ||
    filtros.estado !== "" ||
    filtros.iafas_codigo !== "" ||
    filtros.fecha !== ""
  );
}

function BotonLimpiarFiltros({
  filtros,
  busqueda,
  al_limpiar,
}: {
  filtros: FiltrosCuentas;
  busqueda: string;
  al_limpiar: () => void;
}) {
  return (
    <div className={estilos.acciones_filtro}>
      <span className={estilos.acciones_filtro_espaciador} aria-hidden="true">
        &nbsp;
      </span>
      <div className={estilos.fila_boton_limpiar}>
        <Boton
          variante="terciario"
          onClick={al_limpiar}
          disabled={!hay_filtros_activos(filtros, busqueda)}
        >
          Limpiar filtros
        </Boton>
      </div>
    </div>
  );
}

function FiltroEtapa({
  filtros,
  al_cambiar,
}: {
  filtros: FiltrosCuentas;
  al_cambiar: (filtros: FiltrosCuentas) => void;
}) {
  const estado = filtros.estado ? resolver_estado(filtros.estado).texto : "";
  return (
    <div className={estilos.filtro}>
      <Selector
        etiqueta="Etapa"
        opciones={_OPCIONES_ETAPA}
        value={filtros.etapa}
        onChange={(evento) => al_cambiar({ ...filtros, etapa: evento.target.value })}
      />
      {estado ? (
        <button
          type="button"
          className={estilos.etiqueta_filtro}
          onClick={() => al_cambiar({ ...filtros, estado: "" })}
          aria-label={`Quitar el filtro de estado ${estado}`}
        >
          Estado: {estado} ✕
        </button>
      ) : null}
    </div>
  );
}

export function FiltrosBandejaCuentas({
  filtros,
  al_cambiar,
  busqueda,
  al_cambiar_busqueda,
  al_limpiar,
}: Propiedades) {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });

  return (
    <div className={estilos.filtros}>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => al_cambiar_busqueda(evento.target.value)}
          placeholder="Identificación o asegurado"
        />
      </div>
      <FiltroEtapa filtros={filtros} al_cambiar={al_cambiar} />
      <div className={estilos.filtro}>
        <Selector
          etiqueta="IAFAS"
          opciones={construir_opciones_iafas(consulta_iafas.data ?? [])}
          value={filtros.iafas_codigo}
          onChange={(evento) => al_cambiar({ ...filtros, iafas_codigo: evento.target.value })}
        />
      </div>
      <div className={estilos.filtro}>
        <CampoTexto
          etiqueta="Fecha de prestación"
          type="date"
          value={filtros.fecha}
          onChange={(evento) => al_cambiar({ ...filtros, fecha: evento.target.value })}
        />
      </div>
      <BotonLimpiarFiltros filtros={filtros} busqueda={busqueda} al_limpiar={al_limpiar} />
    </div>
  );
}
