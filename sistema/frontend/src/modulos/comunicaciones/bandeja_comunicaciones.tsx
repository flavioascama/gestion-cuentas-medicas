import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  listar_todas_las_comunicaciones_iafas,
  type ComunicacionIafas,
} from "../../api/comunicaciones_iafas";
import { ControlSegmentado, type OpcionSegmento } from "../../componentes_base/control_segmentado";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { columna_ver, crear_columnas_comunicaciones } from "./columnas_comunicaciones";
import { DialogoComunicacion } from "./dialogo_comunicacion";
import { AccionRevisar } from "./seccion_comunicaciones_iafas";
import { TablaCorreos } from "./tabla_correos";
import estilos from "./comunicaciones.module.css";

// Todo lo que las aseguradoras comunican a la clinica, en una sola
// pantalla (2026-11-15): los correos que una persona debe revisar, todos
// los correos recibidos y las comunicaciones ya registradas en las cuentas.

type Vista = "por_revisar" | "correos" | "registradas";

const _VISTAS: OpcionSegmento<Vista>[] = [
  { valor: "por_revisar", etiqueta: "Por revisar" },
  { valor: "correos", etiqueta: "Correos recibidos" },
  { valor: "registradas", etiqueta: "Registradas en cuentas" },
];

const _COLUMNA_CUENTA: ColumnaTabla<ComunicacionIafas> = {
  clave: "cuenta_medica_id",
  encabezado: "Cuenta",
  formatear: (fila) =>
    fila.cuenta_medica_id ? (
      <Link to={`/cuentas/${fila.cuenta_medica_id}`}>
        {fila.identificacion_interna ?? fila.cuenta_medica_id}
      </Link>
    ) : (
      "—"
    ),
};

function ComunicacionesRegistradas() {
  const consulta = useQuery({
    queryKey: ["comunicaciones_iafas", "todas"],
    queryFn: listar_todas_las_comunicaciones_iafas,
  });
  const [abierta, set_abierta] = useState<ComunicacionIafas | null>(null);
  const columnas = [...crear_columnas_comunicaciones(), _COLUMNA_CUENTA, columna_ver(set_abierta)];
  const filas = consulta.data ?? [];
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filas);

  return (
    <>
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="comunicaciones"
      >
        <TablaDatos
          columnas={columnas}
          filas={filas_pagina}
          obtener_clave={(fila) => fila.codigo}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="Sin comunicaciones registradas."
        />
      </ConPaginacion>
      {abierta !== null ? (
        <DialogoComunicacion comunicacion={abierta} al_cerrar={() => set_abierta(null)} />
      ) : null}
    </>
  );
}

function ContenidoVista({ vista }: { vista: Vista }) {
  if (vista === "registradas") return <ComunicacionesRegistradas />;
  if (vista === "correos") {
    return <TablaCorreos filtro={{}} mostrar_cuenta mensaje_vacio="Sin correos recibidos." />;
  }
  return (
    <TablaCorreos
      filtro={{ estado: "POR_REVISAR" }}
      mostrar_cuenta={false}
      mensaje_vacio="Sin correos por revisar."
    />
  );
}

export function BandejaComunicaciones() {
  const [vista, set_vista] = useState<Vista>("por_revisar");

  return (
    <div>
      <TituloPagina titulo="Comunicaciones" />
      <div className={estilos.seccion}>
        <AccionRevisar />
        <div className={estilos.filtro}>
          <ControlSegmentado
            opciones={_VISTAS}
            valor={vista}
            al_cambiar={set_vista}
            etiqueta_accesible="Comunicaciones que se muestran"
          />
        </div>
        <ContenidoVista vista={vista} />
      </div>
    </div>
  );
}
