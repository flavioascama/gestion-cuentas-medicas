import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { BarraRecorrido } from "../../componentes_base/barra_recorrido";
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
  IconoProcedimientos,
} from "./iconos_detalle_cuenta";
import { SeccionProcedimientos } from "./listas_cuenta";
import { SeccionFarmacia } from "./seccion_farmacia";
import { AvisoRechazoCuenta } from "./aviso_rechazo_cuenta";
import { LineaPasosCuenta } from "./linea_pasos_cuenta";
import { PlazoCuenta } from "./plazo_cuenta";
import { DatosCuenta } from "./secciones_detalle_cuenta";
import { usar_detalle_cuenta, usar_vencimientos } from "./usar_cuentas";
import estilos from "./detalle_cuenta.module.css";

// Orden del detalle (pedido del usuario, 2026-11-18): los datos de la cuenta
// arriba, luego la linea de pasos (que reemplaza a los recuadros de
// completitud, acreditacion, comprobante y carta de garantia) y despues las
// pestanias de trabajo, para llegar a ellas sin desplazarse. La visibilidad
// de cada pestania reusa el mismo predicado que ya decide si su seccion se
// muestra (exportado desde su propio modulo), para no duplicar la regla de
// rol y estado.
function incluir_si(condicion: boolean, pestana: DefinicionPestana): DefinicionPestana | null {
  return condicion ? pestana : null;
}

// Lo que se cruza con la IAFAS va en una sola pestania (2026-11-18): sus
// observaciones, lo que comunico por su portal y sus correos. Cada bloque
// conserva su propia regla de acceso.
function pestana_iafas(
  sesion: ReturnType<typeof usar_sesion>["sesion"],
  cuenta_id: number,
  estado: string,
): DefinicionPestana | null {
  const observaciones = tiene_acceso_observaciones(sesion);
  const comunicaciones = tiene_acceso_comunicaciones(sesion);
  return incluir_si(observaciones || comunicaciones, {
    id: "iafas",
    etiqueta: "IAFAS",
    icono: IconoComunicaciones,
    contenido: (
      <>
        {observaciones ? <SeccionObservaciones cuenta_id={cuenta_id} estado={estado} /> : null}
        {comunicaciones ? <SeccionComunicacionesIafas cuenta_id={cuenta_id} /> : null}
      </>
    ),
  });
}

function usar_pestanas_detalle(
  cuenta: ReturnType<typeof usar_detalle_cuenta>["data"],
  cuenta_id: number,
  al_codificar: () => void,
): DefinicionPestana[] {
  const { sesion } = usar_sesion();
  if (!cuenta) return [];

  const clinicas = !cuenta.datos_clinicos_reservados;
  const candidatas: (DefinicionPestana | null)[] = [
    incluir_si(clinicas, {
      id: "procedimientos",
      etiqueta: "Procedimientos",
      icono: IconoProcedimientos,
      contenido: <SeccionProcedimientos cuenta={cuenta} al_codificar={al_codificar} />,
    }),
    incluir_si(clinicas, {
      id: "farmacia",
      etiqueta: "Farmacia",
      icono: IconoFarmacia,
      contenido: <SeccionFarmacia cuenta={cuenta} />,
    }),
    pestana_iafas(sesion, cuenta_id, cuenta.estado),
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
}

function EncabezadoCuenta({ cuenta, recorrido }: PropiedadesEncabezado) {
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
      <TituloPagina titulo={`Cuenta ${cuenta.identificacion_interna}`} />
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
  const abrir_asistente_cpms = () => set_mostrar_asistente_cpms(true);
  const pestanas = usar_pestanas_detalle(consulta.data, cuenta_id, abrir_asistente_cpms);
  // Abierta desde un aviso o desde un lote: migas, "volver" y anterior o
  // siguiente de esa lista (navegacion/recorrido.ts).
  const recorrido = leer_recorrido(useLocation().state);

  if (consulta.isPending) return <p>Cargando cuenta…</p>;
  if (consulta.isError || !consulta.data)
    return <Mensaje tipo="error" texto="No se pudo cargar la cuenta." />;

  const cuenta = consulta.data;

  return (
    <div>
      <EncabezadoCuenta cuenta={cuenta} recorrido={recorrido} />
      <DatosCuenta cuenta={cuenta} />
      <LineaPasosCuenta
        cuenta_id={cuenta_id}
        estado={cuenta.estado}
        al_codificar={abrir_asistente_cpms}
      />
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
