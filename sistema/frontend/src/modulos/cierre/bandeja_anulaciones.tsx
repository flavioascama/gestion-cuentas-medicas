import { useState } from "react";
import { Link } from "react-router-dom";
import type { SolicitudAnulacion } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { DialogoResolverAnulacion } from "./dialogo_resolver_anulacion";
import { usar_anulaciones_pendientes } from "./usar_cierre";
import estilos from "./bandeja_anulaciones.module.css";

interface Resolucion {
  solicitud_id: number;
  cuenta_medica_id: number;
  aprobada: boolean;
}

function AccionesSolicitud({
  solicitud,
  puede_aprobar,
  al_elegir,
}: {
  solicitud: SolicitudAnulacion;
  puede_aprobar: boolean;
  al_elegir: (resolucion: Resolucion) => void;
}) {
  return (
    <div className={estilos.fila_accion}>
      {puede_aprobar ? (
        <Boton
          variante="secundario"
          onClick={() =>
            al_elegir({
              solicitud_id: solicitud.id,
              cuenta_medica_id: solicitud.cuenta_medica_id,
              aprobada: true,
            })
          }
        >
          Aprobar
        </Boton>
      ) : null}
      <Boton
        variante="destructivo"
        onClick={() =>
          al_elegir({
            solicitud_id: solicitud.id,
            cuenta_medica_id: solicitud.cuenta_medica_id,
            aprobada: false,
          })
        }
      >
        Rechazar
      </Boton>
    </div>
  );
}

// Lo que se anula (2026-11-19): estado, comprobante vigente y nota de credito.
const _COLUMNAS_DOCUMENTOS: ColumnaTabla<SolicitudAnulacion>[] = [
  {
    clave: "estado_cuenta",
    encabezado: "Estado",
    formatear: (fila) =>
      fila.estado_cuenta ? <EtiquetaEstado estado={fila.estado_cuenta} /> : "—",
  },
  { clave: "comprobante", encabezado: "Comprobante", formatear: (fila) => fila.comprobante ?? "—" },
  {
    clave: "nota_credito",
    encabezado: "Nota de crédito",
    formatear: (fila) => fila.nota_credito ?? "—",
  },
];

function construir_columnas(
  al_elegir: (resolucion: Resolucion) => void,
  nombre_usuario: string | undefined,
): ColumnaTabla<SolicitudAnulacion>[] {
  return [
    {
      clave: "cuenta_medica_id",
      encabezado: "Cuenta",
      formatear: (fila) => (
        <Link to={`/cuentas/${fila.cuenta_medica_id}`}>
          {fila.identificacion_interna ?? fila.cuenta_medica_id}
        </Link>
      ),
    },
    { clave: "asegurado", encabezado: "Asegurado", formatear: (fila) => fila.asegurado ?? "—" },
    ..._COLUMNAS_DOCUMENTOS,
    { clave: "motivo", encabezado: "Motivo" },
    {
      clave: "solicitado_por",
      encabezado: "Solicitado por",
      formatear: (fila) => fila.solicitado_por_nombre ?? fila.solicitado_por,
    },
    {
      clave: "solicitado_en",
      encabezado: "Solicitado",
      formatear: (fila) => formatear_fecha_hora(fila.solicitado_en),
    },
    {
      clave: "id",
      encabezado: "Acciones",
      formatear: (fila) => (
        <AccionesSolicitud
          solicitud={fila}
          // Quien la solicito no la aprueba.
          puede_aprobar={fila.solicitado_por !== nombre_usuario}
          al_elegir={al_elegir}
        />
      ),
    },
  ];
}

export function BandejaAnulaciones() {
  const consulta = usar_anulaciones_pendientes();
  const [resolucion, set_resolucion] = useState<Resolucion | null>(null);
  const { sesion } = usar_sesion();
  const columnas = construir_columnas(set_resolucion, sesion?.nombre_usuario);

  const solicitudes = consulta.data ?? [];
  const {
    pagina_actual,
    total_paginas,
    filas_pagina: solicitudes_pagina,
    set_pagina,
  } = usar_pagina_cliente(solicitudes);

  return (
    <div className={estilos.panel}>
      <TituloPagina titulo="Solicitudes de anulación" />
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={solicitudes.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="solicitudes"
      >
        <TablaDatos
          columnas={columnas}
          filas={solicitudes_pagina}
          obtener_clave={(fila) => fila.id}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="No hay solicitudes de anulación pendientes."
        />
      </ConPaginacion>
      {resolucion ? (
        <DialogoResolverAnulacion
          solicitud_id={resolucion.solicitud_id}
          cuenta_medica_id={resolucion.cuenta_medica_id}
          aprobada={resolucion.aprobada}
          al_cerrar={() => set_resolucion(null)}
          al_resolver={() => set_resolucion(null)}
        />
      ) : null}
    </div>
  );
}
