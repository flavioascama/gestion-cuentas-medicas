import { useState } from "react";
import type { EstadoCierre } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { es_visible_cierre_anulacion, usar_estado_cierre } from "./usar_cierre";
import { DialogoConfirmarCierre } from "./dialogo_confirmar_cierre";
import { DialogoSolicitarAnulacion } from "./dialogo_solicitar_anulacion";

const _ESTADOS_CIERRE = new Set(["PAGADA", "PAGADA_PARCIAL"]);
const _LISTA = new Intl.ListFormat("es", { type: "conjunction" });

// Lo que falta antes de cerrar, con el mismo formato que los pasos de la cuenta.
function faltantes_cierre(cierre: EstadoCierre): string[] {
  const faltantes: string[] = [];
  if (!cierre.pago_conciliado) faltantes.push("conciliar el pago");
  if (cierre.diferencia !== null) {
    const monto = formatear_monto(Math.abs(Number(cierre.diferencia)));
    faltantes.push(`resolver la diferencia de ${monto} entre lo liquidado y lo pagado`);
  }
  const abiertas = cierre.observaciones_sin_responder;
  if (abiertas === 1) faltantes.push("responder 1 observación");
  if (abiertas > 1) faltantes.push(`responder ${abiertas} observaciones`);
  return faltantes;
}

function CerrarCuenta({ cierre, al_cerrar }: { cierre?: EstadoCierre; al_cerrar: () => void }) {
  const faltantes = cierre ? faltantes_cierre(cierre) : [];
  return (
    <>
      <Boton variante="secundario" onClick={al_cerrar} disabled={!cierre || faltantes.length > 0}>
        Cerrar cuenta
      </Boton>
      {faltantes.length > 0 ? <span>Antes falta: {_LISTA.format(faltantes)}.</span> : null}
    </>
  );
}

function SolicitudResuelta({ cierre }: { cierre?: EstadoCierre }) {
  const solicitud = cierre?.ultima_solicitud;
  if (solicitud?.estado !== "RECHAZADA" || !solicitud.resuelto_en) return null;
  const motivo = solicitud.motivo_resolucion ? ` Motivo: ${solicitud.motivo_resolucion}` : "";
  return (
    <p>
      Anulación rechazada el {formatear_fecha_hora(solicitud.resuelto_en)} por{" "}
      {solicitud.resuelto_por}.{motivo}
    </p>
  );
}

// Con una solicitud pendiente no se ofrece otra.
function SolicitarAnulacion({
  cierre,
  al_solicitar,
}: {
  cierre?: EstadoCierre;
  al_solicitar: () => void;
}) {
  const solicitud = cierre?.ultima_solicitud;
  if (solicitud?.estado === "PENDIENTE") {
    return (
      <span>
        Anulación solicitada el {formatear_fecha_hora(solicitud.solicitado_en)} por{" "}
        {solicitud.solicitado_por}.
      </span>
    );
  }
  return (
    <Boton variante="destructivo" onClick={al_solicitar} disabled={!cierre}>
      Solicitar anulación
    </Boton>
  );
}

export function SeccionCierreAnulacion({
  cuenta_id,
  estado,
}: {
  cuenta_id: number;
  estado: string;
}) {
  const { sesion } = usar_sesion();
  const visible = es_visible_cierre_anulacion(sesion, estado);
  const cierre = usar_estado_cierre(cuenta_id, visible).data;
  const [mostrar_cierre, set_mostrar_cierre] = useState(false);
  const [mostrar_anulacion, set_mostrar_anulacion] = useState(false);

  if (!visible) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Cierre y anulación</div>
      <div className={estilos.fila_accion}>
        {_ESTADOS_CIERRE.has(estado) ? (
          <CerrarCuenta cierre={cierre} al_cerrar={() => set_mostrar_cierre(true)} />
        ) : null}
        <SolicitarAnulacion cierre={cierre} al_solicitar={() => set_mostrar_anulacion(true)} />
      </div>
      <SolicitudResuelta cierre={cierre} />
      {mostrar_cierre ? (
        <DialogoConfirmarCierre
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_cierre(false)}
          al_confirmar={() => set_mostrar_cierre(false)}
        />
      ) : null}
      {mostrar_anulacion ? (
        <DialogoSolicitarAnulacion
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_anulacion(false)}
          al_solicitar={() => set_mostrar_anulacion(false)}
        />
      ) : null}
    </div>
  );
}
