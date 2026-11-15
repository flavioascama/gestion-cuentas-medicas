import { useState } from "react";
import type { Observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { DialogoAsignarObservacion } from "./dialogo_asignar_observacion";
import { DialogoRegistrarObservacion } from "./dialogo_registrar_observacion";
import { DialogoResponderObservacion } from "./dialogo_responder_observacion";
import { ResultadoAuditoria } from "./resultado_auditoria";
import { usar_observaciones_cuenta, tiene_acceso_observaciones } from "./usar_observaciones";

const _ETIQUETA_NATURALEZA: Record<string, string> = {
  ADMINISTRATIVA: "Administrativa",
  TECNICA: "Técnica",
  FINANCIERA: "Financiera",
};

const _ETIQUETA_ESTADO: Record<string, string> = {
  ABIERTA: "Abierta",
  RESPONDIDA: "Respondida",
};

function AccionesObservacion({
  observacion,
  puede_asignar,
  puede_responder,
  al_abrir_asignar,
  al_abrir_responder,
}: {
  observacion: Observacion;
  puede_asignar: boolean;
  puede_responder: boolean;
  al_abrir_asignar: (id: number) => void;
  al_abrir_responder: (id: number) => void;
}) {
  if (observacion.estado !== "ABIERTA") return null;
  return (
    <div className={estilos.fila_accion}>
      {puede_asignar ? (
        <Boton variante="terciario" onClick={() => al_abrir_asignar(observacion.id)}>
          Asignar
        </Boton>
      ) : null}
      {puede_responder ? (
        <Boton variante="terciario" onClick={() => al_abrir_responder(observacion.id)}>
          Responder
        </Boton>
      ) : null}
    </div>
  );
}

function crear_columnas(
  puede_asignar: boolean,
  puede_responder: boolean,
  al_abrir_asignar: (id: number) => void,
  al_abrir_responder: (id: number) => void,
): ColumnaTabla<Observacion>[] {
  return [
    {
      clave: "naturaleza",
      encabezado: "Naturaleza",
      formatear: (fila) => _ETIQUETA_NATURALEZA[fila.naturaleza] ?? fila.naturaleza,
    },
    { clave: "motivo_codigo", encabezado: "Motivo" },
    {
      clave: "estado",
      encabezado: "Estado",
      formatear: (fila) => _ETIQUETA_ESTADO[fila.estado] ?? fila.estado,
    },
    { clave: "responsable_rol", encabezado: "Responsable" },
    {
      clave: "registrado_en",
      encabezado: "Registrada",
      formatear: (fila) => formatear_fecha_hora(fila.registrado_en),
    },
    {
      clave: "respondido_en",
      encabezado: "Respondida",
      formatear: (fila) => (fila.respondido_en ? formatear_fecha_hora(fila.respondido_en) : "—"),
    },
    {
      clave: "id",
      encabezado: "Acciones",
      formatear: (fila) => (
        <AccionesObservacion
          observacion={fila}
          puede_asignar={puede_asignar}
          puede_responder={puede_responder}
          al_abrir_asignar={al_abrir_asignar}
          al_abrir_responder={al_abrir_responder}
        />
      ),
    },
  ];
}

interface EstadoDialogos {
  mostrar_registro: boolean;
  set_mostrar_registro: (valor: boolean) => void;
  asignar_observacion_id: number | null;
  set_asignar_observacion_id: (valor: number | null) => void;
  responder_observacion_id: number | null;
  set_responder_observacion_id: (valor: number | null) => void;
}

function DialogosObservaciones({
  cuenta_id,
  estado,
}: {
  cuenta_id: number;
  estado: EstadoDialogos;
}) {
  return (
    <>
      {estado.mostrar_registro ? (
        <DialogoRegistrarObservacion
          cuenta_id={cuenta_id}
          al_cerrar={() => estado.set_mostrar_registro(false)}
          al_registrar={() => estado.set_mostrar_registro(false)}
        />
      ) : null}
      {estado.asignar_observacion_id !== null ? (
        <DialogoAsignarObservacion
          cuenta_id={cuenta_id}
          observacion_id={estado.asignar_observacion_id}
          al_cerrar={() => estado.set_asignar_observacion_id(null)}
          al_asignar={() => estado.set_asignar_observacion_id(null)}
        />
      ) : null}
      {estado.responder_observacion_id !== null ? (
        <DialogoResponderObservacion
          cuenta_id={cuenta_id}
          observacion_id={estado.responder_observacion_id}
          al_cerrar={() => estado.set_responder_observacion_id(null)}
          al_responder={() => estado.set_responder_observacion_id(null)}
        />
      ) : null}
    </>
  );
}

export function SeccionObservaciones({ cuenta_id, estado }: { cuenta_id: number; estado: string }) {
  const { sesion } = usar_sesion();
  const consulta = usar_observaciones_cuenta(cuenta_id);
  const [mostrar_registro, set_mostrar_registro] = useState(false);
  const [asignar_observacion_id, set_asignar_observacion_id] = useState<number | null>(null);
  const [responder_observacion_id, set_responder_observacion_id] = useState<number | null>(null);

  if (!tiene_acceso_observaciones(sesion) || !sesion) return null;

  const puede_registrar = sesion.roles.includes("analista");
  const columnas = crear_columnas(
    sesion.roles.includes("jefe"),
    sesion.roles.includes("analista") || sesion.roles.includes("auditor"),
    set_asignar_observacion_id,
    set_responder_observacion_id,
  );

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Observaciones de la IAFAS</div>
      <ResultadoAuditoria
        cuenta_id={cuenta_id}
        estado={estado}
        puede_registrar={puede_registrar}
        al_registrar_observacion={() => set_mostrar_registro(true)}
      />
      <TablaDatos
        columnas={columnas}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="La IAFAS no ha comunicado observaciones sobre esta cuenta."
      />
      <DialogosObservaciones
        cuenta_id={cuenta_id}
        estado={{
          mostrar_registro,
          set_mostrar_registro,
          asignar_observacion_id,
          set_asignar_observacion_id,
          responder_observacion_id,
          set_responder_observacion_id,
        }}
      />
    </div>
  );
}
