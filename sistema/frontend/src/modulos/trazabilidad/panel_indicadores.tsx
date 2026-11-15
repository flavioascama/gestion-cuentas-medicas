import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { IndicadoresCiclo } from "../../api/trazabilidad";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { BarraFiltros, type FiltrosPanel } from "./barra_filtros";
import { GraficosPanel } from "./graficos_panel";
import { SeccionCicloCuenta } from "./seccion_ciclo_cuenta";
import { FilaKpi } from "./tarjetas_kpi";
import { usar_indicadores } from "./usar_trazabilidad";
import estilos from "./panel_indicadores.module.css";

type ConsultaIndicadores = UseQueryResult<IndicadoresCiclo>;

// C-18: los resultados registrados en modo de contingencia "quedan
// marcados como registro manual... en el panel de control gerencial".
function AvisoContingencia({ indicadores }: { indicadores: IndicadoresCiclo }) {
  const { total, pendientes_revision } = indicadores.registros_contingencia;
  if (total === 0) return null;
  const registrados =
    total === 1
      ? "1 resultado de este filtro se registró"
      : `${total} resultados de este filtro se registraron`;
  const pendientes =
    pendientes_revision === 0
      ? ""
      : `, ${pendientes_revision} ${pendientes_revision === 1 ? "pendiente" : "pendientes"} de revisión`;
  return (
    <Mensaje
      tipo="advertencia"
      texto={`${registrados} a mano en modo de contingencia${pendientes}.`}
    />
  );
}

function EstadoActualizacion({ consulta }: { consulta: ConsultaIndicadores }) {
  if (!consulta.data) return null;
  return (
    <div className={estilos.actualizacion}>
      <span className={estilos.actualizado}>
        Actualizado {formatear_fecha_hora(new Date(consulta.dataUpdatedAt).toISOString())}
      </span>
      <Boton
        variante="secundario"
        onClick={() => void consulta.refetch()}
        disabled={consulta.isFetching}
      >
        Actualizar
      </Boton>
    </div>
  );
}

interface PropiedadesContenido {
  consulta: ConsultaIndicadores;
  filtros: FiltrosPanel;
  al_alternar: (campo: keyof FiltrosPanel, valor: string) => void;
  al_ver_cuentas: (estado: string) => void;
}

// Al cambiar un filtro se conserva el panel anterior atenuado mientras
// llegan los datos nuevos (sin parpadeo ni salto de altura).
function ContenidoPanel({ consulta, filtros, al_alternar, al_ver_cuentas }: PropiedadesContenido) {
  if (consulta.isPending) return <p className={estilos.carga}>Cargando indicadores…</p>;
  if (!consulta.data) {
    return <Mensaje tipo="error" texto="No se pudo obtener los indicadores. Intente nuevamente." />;
  }
  return (
    <div
      className={consulta.isPlaceholderData ? estilos.recargando : undefined}
      aria-busy={consulta.isFetching}
    >
      <FilaKpi indicadores={consulta.data} periodo={filtros.periodo} />
      <AvisoContingencia indicadores={consulta.data} />
      <GraficosPanel
        indicadores={consulta.data}
        filtros={filtros}
        al_alternar_periodo={(periodo) => al_alternar("periodo", periodo)}
        al_alternar_iafas={(codigo) => al_alternar("iafas_codigo", codigo)}
        al_ver_cuentas={al_ver_cuentas}
      />
      <SeccionCicloCuenta indicadores={consulta.data} />
    </div>
  );
}

export function PanelIndicadores() {
  const navegar = useNavigate();
  const [filtros, set_filtros] = useState<FiltrosPanel>({ iafas_codigo: "", periodo: "" });
  const consulta = usar_indicadores({
    iafas_codigo: filtros.iafas_codigo || undefined,
    periodo: filtros.periodo || undefined,
  });

  // Pulsar de nuevo lo ya elegido quita ese filtro.
  const alternar = (campo: keyof FiltrosPanel, valor: string) =>
    set_filtros((previos) => ({ ...previos, [campo]: previos[campo] === valor ? "" : valor }));

  const ver_cuentas = (estado: string) => {
    const parametros = new URLSearchParams({ estado });
    if (filtros.iafas_codigo) parametros.set("iafas", filtros.iafas_codigo);
    void navegar(`/cuentas?${parametros.toString()}`);
  };

  return (
    <div>
      <TituloPagina
        titulo="Panel de control gerencial"
        acciones={<EstadoActualizacion consulta={consulta} />}
      />
      <BarraFiltros filtros={filtros} al_cambiar={set_filtros} />
      <ContenidoPanel
        consulta={consulta}
        filtros={filtros}
        al_alternar={alternar}
        al_ver_cuentas={ver_cuentas}
      />
    </div>
  );
}
