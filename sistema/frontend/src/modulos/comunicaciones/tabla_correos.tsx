import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  listar_correos_iafas,
  type CorreoIafas,
  type FiltroCorreos,
} from "../../api/correos_iafas";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { Paginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { DialogoCorreo } from "./dialogo_correo";
import { MOTIVOS_REVISION } from "./etiquetas_correos";
import estilos from "./comunicaciones.module.css";

// Correos que llegaron al buzon de cuentas medicas: tambien los que el
// robot no pudo aplicar solo, que quedan por revisar (2026-11-15).

const _COLUMNAS_BASE: ColumnaTabla<CorreoIafas>[] = [
  {
    clave: "recibido_en",
    encabezado: "Recibido",
    formatear: (fila) => formatear_fecha_hora(fila.recibido_en),
  },
  {
    clave: "remitente",
    encabezado: "Remitente",
    formatear: (fila) => (
      <>
        {fila.remitente}
        {fila.codigo_iafas ? (
          <span className={estilos.dato_secundario}>Aseguradora {fila.codigo_iafas}</span>
        ) : null}
      </>
    ),
  },
  { clave: "asunto", encabezado: "Asunto", formatear: (fila) => fila.asunto || "(Sin asunto)" },
  { clave: "cantidad_adjuntos", encabezado: "Adjuntos" },
  {
    clave: "estado",
    encabezado: "Estado",
    formatear: (fila) => (
      <>
        <EtiquetaEstado estado={fila.estado} />
        {fila.motivo_revision ? (
          <span className={estilos.dato_secundario}>
            {MOTIVOS_REVISION[fila.motivo_revision] ?? fila.motivo_revision}
          </span>
        ) : null}
      </>
    ),
  },
];

const _COLUMNA_CUENTA: ColumnaTabla<CorreoIafas> = {
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

function columnas(
  mostrar_cuenta: boolean,
  al_ver: (correo: CorreoIafas) => void,
): ColumnaTabla<CorreoIafas>[] {
  const ver: ColumnaTabla<CorreoIafas> = {
    clave: "id",
    encabezado: "",
    formatear: (fila) => (
      <Boton variante="terciario" onClick={() => al_ver(fila)}>
        Ver
      </Boton>
    ),
  };
  return mostrar_cuenta ? [..._COLUMNAS_BASE, _COLUMNA_CUENTA, ver] : [..._COLUMNAS_BASE, ver];
}

interface Propiedades {
  filtro: FiltroCorreos;
  mostrar_cuenta: boolean;
  mensaje_vacio: string;
}

export function TablaCorreos({ filtro, mostrar_cuenta, mensaje_vacio }: Propiedades) {
  const consulta = useQuery({
    queryKey: ["correos_iafas", filtro.estado ?? "TODOS", filtro.cuenta_id ?? 0],
    queryFn: () => listar_correos_iafas(filtro),
  });
  const [abierto, set_abierto] = useState<number | null>(null);
  const filas = consulta.data ?? [];
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filas);

  return (
    <>
      <TablaDatos
        columnas={columnas(mostrar_cuenta, (correo) => set_abierto(correo.id))}
        filas={filas_pagina}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio={mensaje_vacio}
      />
      <Paginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="correos"
      />
      {abierto !== null ? (
        <DialogoCorreo correo_id={abierto} al_cerrar={() => set_abierto(null)} />
      ) : null}
    </>
  );
}
