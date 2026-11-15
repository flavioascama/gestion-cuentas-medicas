import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router-dom";
import { listar_iafas } from "../../api/iafas";
import { ErrorApi } from "../../api/cliente_http";
import { BarraRecorrido } from "../../componentes_base/barra_recorrido";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { LineaEstadosLote } from "../../componentes_base/linea_estados_lote";
import { Mensaje } from "../../componentes_base/mensaje";
import { MigasPan } from "../../componentes_base/migas_pan";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { leer_recorrido, migas_con_recorrido } from "../../navegacion/recorrido";
import { AccionValidacionContingencia } from "../contingencia/accion_validacion_contingencia";
import { SeccionHistorialLote } from "../trazabilidad/seccion_historial_lote";
import { calcular_pasos_lote } from "./calcular_pasos_lote";
import { SeccionCuentasLote } from "./seccion_cuentas_lote";
import { BotonAccionLote, ContenidoAccionLote, usar_acciones_lote } from "./seccion_acciones_lote";
import { SeccionAcuses, SeccionDatosLote, SeccionObservaciones } from "./secciones_detalle_lote";
import {
  usar_acuses_lote,
  usar_detalle_lote,
  usar_prevalidacion_lote,
  usar_validacion_oficial_lote,
} from "./usar_lotes";
import estilos from "./detalle_lote.module.css";

function es_prevalidacion_no_encontrada(error: unknown): boolean {
  return error instanceof ErrorApi && error.estado_http === 404;
}

// El codigo crudo de la IAFAS (lo unico que trae DetalleLoteRespuesta)
// se resuelve contra el mismo listado que ya usan los filtros de
// Cuentas/Lotes -- sin pedirle al backend un campo que ya es derivable
// en el cliente (Fase 18 dejo esta ruta solo con el codigo).
function usar_nombre_iafas(codigo: string): string {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  const iafas = (consulta_iafas.data ?? []).find((i) => i.codigo === codigo);
  return iafas ? `${iafas.codigo} — ${iafas.razon_social}` : codigo;
}

function EtiquetasLote({ lote }: { lote: { estado: string; monitoreo_excedido: boolean } }) {
  return (
    <>
      <EtiquetaEstado estado={lote.estado} />
      {lote.monitoreo_excedido ? <EtiquetaEstado estado="EXCEDIDO" /> : null}
    </>
  );
}

export function DetalleLote() {
  const parametros = useParams<{ lote_id: string }>();
  const lote_id = Number(parametros.lote_id);

  const consulta_lote = usar_detalle_lote(lote_id);
  const consulta_prevalidacion = usar_prevalidacion_lote(lote_id);
  const consulta_validaciones = usar_validacion_oficial_lote(lote_id);
  const consulta_acuses = usar_acuses_lote(lote_id);
  const acciones = usar_acciones_lote(lote_id);
  const nombre_iafas = usar_nombre_iafas(consulta_lote.data?.iafas_codigo ?? "");
  const recorrido = leer_recorrido(useLocation().state);

  if (consulta_lote.isPending) return <p>Cargando lote…</p>;
  if (consulta_lote.isError || !consulta_lote.data)
    return <Mensaje tipo="error" texto="No se pudo cargar el lote." />;

  const lote = consulta_lote.data;
  const observaciones = (consulta_validaciones.data ?? []).flatMap((v) => v.observaciones);
  const pasos = calcular_pasos_lote(
    lote,
    consulta_prevalidacion.data,
    es_prevalidacion_no_encontrada(consulta_prevalidacion.error),
    consulta_validaciones.data ?? [],
    consulta_acuses.data ?? [],
  );

  return (
    <div>
      <MigasPan
        migas={migas_con_recorrido(recorrido, [{ etiqueta: "Lotes", ruta: "/lotes" }], lote.numero)}
      />
      <BarraRecorrido recorrido={recorrido} />
      <TituloPagina
        titulo={`Lote ${lote.numero}`}
        acciones={
          <div className={estilos.acciones}>
            <EtiquetasLote lote={lote} />
            <BotonAccionLote estado={lote.estado} acciones={acciones} />
          </div>
        }
      />
      <LineaEstadosLote pasos={pasos} />
      <ContenidoAccionLote estado={lote.estado} acciones={acciones} />
      <AccionValidacionContingencia lote_id={lote.id} />
      <SeccionDatosLote lote={lote} nombre_iafas={nombre_iafas} />
      <SeccionCuentasLote lote_id={lote_id} numero={lote.numero} />
      <SeccionObservaciones observaciones={observaciones} />
      <SeccionAcuses acuses={consulta_acuses.data ?? []} />
      <SeccionHistorialLote lote_id={lote_id} />
    </div>
  );
}
