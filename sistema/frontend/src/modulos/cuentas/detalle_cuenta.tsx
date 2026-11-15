import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { BarraRecorrido } from "../../componentes_base/barra_recorrido";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { Mensaje } from "../../componentes_base/mensaje";
import { MigasPan } from "../../componentes_base/migas_pan";
import { Pestanas, type DefinicionPestana } from "../../componentes_base/pestanas";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { AsistenteCpms } from "../codificacion/asistente_cpms";
import { leer_recorrido, migas_con_recorrido, type Recorrido } from "../../navegacion/recorrido";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { SeccionCierreAnulacion } from "../cierre/seccion_cierre_anulacion";
import { tiene_acceso_comunicaciones } from "../comunicaciones/acceso_comunicaciones";
import { SeccionComunicacionesIafas } from "../comunicaciones/seccion_comunicaciones_iafas";
import { es_visible_cierre_anulacion } from "../cierre/usar_cierre";
import { SeccionLiquidacion } from "../liquidacion/seccion_liquidacion";
import { SeccionObservaciones } from "../observaciones/seccion_observaciones";
import { tiene_acceso_observaciones } from "../observaciones/usar_observaciones";
import { SeccionHistorial } from "../trazabilidad/seccion_historial";
import { tiene_acceso_historial } from "../trazabilidad/usar_trazabilidad";
import {
  IconoCierre,
  IconoComunicaciones,
  IconoFarmacia,
  IconoHistorial,
  IconoLiquidacion,
  IconoObservaciones,
  IconoProcedimientos,
} from "./iconos_detalle_cuenta";
import { SeccionProcedimientos } from "./listas_cuenta";
import { SeccionFarmacia } from "./seccion_farmacia";
import { AvisoRechazoCuenta } from "./aviso_rechazo_cuenta";
import { PanelCompletitudCuenta } from "./panel_completitud_cuenta";
import { PlazoCuenta } from "./plazo_cuenta";
import { SeccionAcreditacion } from "./seccion_acreditacion";
import { SeccionComprobante } from "./seccion_comprobante";
import { DatosCuenta } from "./secciones_detalle_cuenta";
import { usar_detalle_cuenta, usar_vencimientos } from "./usar_cuentas";
import { SeccionCartaGarantia } from "./seccion_carta_garantia";
import estilos from "./detalle_cuenta.module.css";

// Estados en que se codifica (Tabla 69: nada despues de CERRADA o
// ANULADA): antes de facturar, al corregir una cuenta rechazada y al
// refacturar por una glosa tecnica. El backend aplica la misma regla.
const _ESTADOS_CODIFICABLES = new Set(["REGISTRADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);

function AccionCodificar({ estado, al_codificar }: { estado: string; al_codificar: () => void }) {
  const { sesion } = usar_sesion();
  if (!sesion?.roles.includes("auditor") || !_ESTADOS_CODIFICABLES.has(estado)) return null;
  return (
    <Boton variante="primario" onClick={al_codificar}>
      Codificar procedimiento
    </Boton>
  );
}

// Rediseno "resumen + pestanias" (confirmado por el usuario frente a la
// alternativa de "todo en pestanias" o "solo cuadricula"): las secciones
// de trabajo (tablas y acciones por etapa) pasan de apilarse todas de
// arriba hacia abajo a vivir detras de una pestania con icono, una por
// bloque -- la cuadricula de resumen de arriba (completitud, cobertura,
// comprobante) sigue siempre visible porque es informacion de un
// vistazo, no un formulario de trabajo. La visibilidad de cada pestania
// reusa el mismo predicado que ya decide si la seccion original se
// renderiza (exportado desde su propio modulo), para no duplicar la
// regla de rol/estado en dos lugares que podrian desalinearse.
function incluir_si(condicion: boolean, pestana: DefinicionPestana): DefinicionPestana | null {
  return condicion ? pestana : null;
}

// Lo que se cruza con la IAFAS: sus observaciones y lo que comunico por
// su portal o por correo.
function pestanas_iafas(
  sesion: ReturnType<typeof usar_sesion>["sesion"],
  cuenta_id: number,
  estado: string,
): (DefinicionPestana | null)[] {
  return [
    incluir_si(tiene_acceso_observaciones(sesion), {
      id: "observaciones",
      etiqueta: "Observaciones",
      icono: IconoObservaciones,
      contenido: <SeccionObservaciones cuenta_id={cuenta_id} estado={estado} />,
    }),
    incluir_si(tiene_acceso_comunicaciones(sesion), {
      id: "comunicaciones",
      etiqueta: "Comunicaciones IAFAS",
      icono: IconoComunicaciones,
      contenido: <SeccionComunicacionesIafas cuenta_id={cuenta_id} />,
    }),
  ];
}

function usar_pestanas_detalle(
  cuenta: ReturnType<typeof usar_detalle_cuenta>["data"],
  cuenta_id: number,
): DefinicionPestana[] {
  const { sesion } = usar_sesion();
  if (!cuenta) return [];

  const clinicas = !cuenta.datos_clinicos_reservados;
  const candidatas: (DefinicionPestana | null)[] = [
    incluir_si(clinicas, {
      id: "procedimientos",
      etiqueta: "Procedimientos",
      icono: IconoProcedimientos,
      contenido: <SeccionProcedimientos cuenta={cuenta} />,
    }),
    incluir_si(clinicas, {
      id: "farmacia",
      etiqueta: "Farmacia",
      icono: IconoFarmacia,
      contenido: <SeccionFarmacia cuenta={cuenta} />,
    }),
    ...pestanas_iafas(sesion, cuenta_id, cuenta.estado),
    {
      id: "liquidacion",
      etiqueta: "Liquidación y pago",
      icono: IconoLiquidacion,
      contenido: <SeccionLiquidacion cuenta_id={cuenta_id} estado={cuenta.estado} />,
    },
    incluir_si(es_visible_cierre_anulacion(sesion, cuenta.estado), {
      id: "cierre",
      etiqueta: "Cierre y anulación",
      icono: IconoCierre,
      contenido: <SeccionCierreAnulacion cuenta_id={cuenta_id} estado={cuenta.estado} />,
    }),
    incluir_si(tiene_acceso_historial(sesion), {
      id: "historial",
      etiqueta: "Historial",
      icono: IconoHistorial,
      contenido: <SeccionHistorial cuenta_id={cuenta_id} />,
    }),
  ];

  return candidatas.filter((pestana): pestana is DefinicionPestana => pestana !== null);
}

interface PropiedadesEncabezado {
  cuenta: NonNullable<ReturnType<typeof usar_detalle_cuenta>["data"]>;
  recorrido: Recorrido | null;
  al_codificar: () => void;
}

function EncabezadoCuenta({ cuenta, recorrido, al_codificar }: PropiedadesEncabezado) {
  const vencimientos = usar_vencimientos();
  return (
    <>
      <MigasPan
        migas={migas_con_recorrido(
          recorrido,
          [{ etiqueta: "Cuentas", ruta: "/cuentas" }],
          cuenta.identificacion_interna,
        )}
      />
      <BarraRecorrido recorrido={recorrido} />
      <TituloPagina
        titulo={`Cuenta ${cuenta.identificacion_interna}`}
        acciones={<AccionCodificar estado={cuenta.estado} al_codificar={al_codificar} />}
      />
      <div className={estilos.fila_accion}>
        <EtiquetaEstado estado={cuenta.estado} />
        <PlazoCuenta vencimiento={vencimientos.get(cuenta.id)} />
      </div>
      <AvisoRechazoCuenta cuenta_id={cuenta.id} estado={cuenta.estado} />
    </>
  );
}

export function DetalleCuenta() {
  const parametros = useParams<{ cuenta_id: string }>();
  const cuenta_id = Number(parametros.cuenta_id);
  const consulta = usar_detalle_cuenta(cuenta_id);
  const [mostrar_asistente_cpms, set_mostrar_asistente_cpms] = useState(false);
  const pestanas = usar_pestanas_detalle(consulta.data, cuenta_id);
  // Abierta desde un aviso o desde un lote: migas, "volver" y anterior o
  // siguiente de esa lista (navegacion/recorrido.ts).
  const recorrido = leer_recorrido(useLocation().state);

  if (consulta.isPending) return <p>Cargando cuenta…</p>;
  if (consulta.isError || !consulta.data)
    return <Mensaje tipo="error" texto="No se pudo cargar la cuenta." />;

  const cuenta = consulta.data;

  return (
    <div>
      <EncabezadoCuenta
        cuenta={cuenta}
        recorrido={recorrido}
        al_codificar={() => set_mostrar_asistente_cpms(true)}
      />
      <div className={estilos.cuadricula_resumen}>
        <PanelCompletitudCuenta
          cuenta_id={cuenta_id}
          al_codificar={() => set_mostrar_asistente_cpms(true)}
        />
        <SeccionAcreditacion cuenta_id={cuenta_id} />
        <SeccionComprobante cuenta_id={cuenta_id} estado={cuenta.estado} />
        <SeccionCartaGarantia cuenta_id={cuenta_id} estado={cuenta.estado} />
      </div>
      <DatosCuenta cuenta={cuenta} />
      <Pestanas pestanas={pestanas} etiqueta_lista="Secciones de la cuenta" />
      <Link to={recorrido?.volver.ruta ?? "/cuentas"}>
        {recorrido?.volver.etiqueta ?? "Volver a la bandeja"}
      </Link>
      {mostrar_asistente_cpms ? (
        <AsistenteCpms cuenta_id={cuenta_id} al_cerrar={() => set_mostrar_asistente_cpms(false)} />
      ) : null}
    </div>
  );
}
