import { useState } from "react";
import { Link } from "react-router-dom";
import type { SolicitudAnulacion } from "../../api/cierre";
import { Boton } from "../../componentes_base/boton";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
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
  al_elegir,
}: {
  solicitud: SolicitudAnulacion;
  al_elegir: (resolucion: Resolucion) => void;
}) {
  return (
    <div className={estilos.fila_accion}>
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

function construir_columnas(
  al_elegir: (resolucion: Resolucion) => void,
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
    { clave: "motivo", encabezado: "Motivo" },
    { clave: "solicitado_por", encabezado: "Solicitado por" },
    {
      clave: "solicitado_en",
      encabezado: "Solicitado",
      formatear: (fila) => formatear_fecha_hora(fila.solicitado_en),
    },
    {
      clave: "id",
      encabezado: "Acciones",
      formatear: (fila) => <AccionesSolicitud solicitud={fila} al_elegir={al_elegir} />,
    },
  ];
}

export function BandejaAnulaciones() {
  const consulta = usar_anulaciones_pendientes();
  const [resolucion, set_resolucion] = useState<Resolucion | null>(null);
  const columnas = construir_columnas(set_resolucion);

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
