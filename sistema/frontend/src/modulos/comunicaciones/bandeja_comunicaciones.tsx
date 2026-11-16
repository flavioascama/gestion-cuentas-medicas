import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  listar_todas_las_comunicaciones_iafas,
  type ComunicacionIafas,
} from "../../api/comunicaciones_iafas";
import { ControlSegmentado, type OpcionSegmento } from "../../componentes_base/control_segmentado";
import { Paginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { COLUMNAS_COMUNICACIONES } from "./columnas_comunicaciones";
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

const _COLUMNAS_REGISTRADAS: ColumnaTabla<ComunicacionIafas>[] = [
  ...COLUMNAS_COMUNICACIONES,
  {
    clave: "cuenta_medica_id",
    encabezado: "Cuenta",
    formatear: (fila) =>
      fila.cuenta_medica_id ? <Link to={`/cuentas/${fila.cuenta_medica_id}`}>Abrir</Link> : "—",
  },
];

function ComunicacionesRegistradas() {
  const consulta = useQuery({
    queryKey: ["comunicaciones_iafas", "todas"],
    queryFn: listar_todas_las_comunicaciones_iafas,
  });
  const filas = consulta.data ?? [];
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filas);

  return (
    <>
      <TablaDatos
        columnas={_COLUMNAS_REGISTRADAS}
        filas={filas_pagina}
        obtener_clave={(fila) => fila.codigo}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="Sin comunicaciones registradas."
      />
      <Paginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="comunicaciones"
      />
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
