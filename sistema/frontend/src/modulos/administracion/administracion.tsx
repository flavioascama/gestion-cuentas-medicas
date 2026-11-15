import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cargar_catalogo_cpms, type VersionCpms } from "../../api/cpms";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { SeccionCatalogoGtin } from "./seccion_catalogo_gtin";
import { SeccionParametros } from "./seccion_parametros";
import { SeccionUsuarios } from "./seccion_usuarios";
import { usar_versiones_cpms } from "./usar_administracion";
import estilos from "./administracion.module.css";

const _COLUMNAS_CPMS: ColumnaTabla<VersionCpms>[] = [
  { clave: "etiqueta", encabezado: "Versión" },
  { clave: "conteo", encabezado: "Procedimientos", alinear_derecha: true },
  {
    clave: "creado_en",
    encabezado: "Cargado",
    formatear: (fila) => formatear_fecha_hora(fila.creado_en),
  },
];

function SeccionCatalogoCpms() {
  const cliente_consultas = useQueryClient();
  const consulta_cpms = usar_versiones_cpms();

  const mutacion_cargar_cpms = useMutation({
    mutationFn: () => cargar_catalogo_cpms(),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({ queryKey: ["administracion", "cpms"] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Catálogo CPMS</div>
      <MensajeErrorMutacion
        error={mutacion_cargar_cpms.error}
        texto_por_defecto="No se pudo cargar el catálogo."
      />
      <Boton
        variante="secundario"
        onClick={() => mutacion_cargar_cpms.mutate()}
        disabled={mutacion_cargar_cpms.isPending}
      >
        Cargar nueva versión desde docs/fuentes
      </Boton>
      <TablaDatos
        columnas={_COLUMNAS_CPMS}
        filas={consulta_cpms.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={consulta_cpms.isPending}
        error={consulta_cpms.error}
        mensaje_vacio="No hay versiones del catálogo CPMS cargadas."
      />
    </div>
  );
}

export function Administracion() {
  return (
    <div>
      <TituloPagina titulo="Administración" />
      <SeccionUsuarios />
      <SeccionParametros />
      <SeccionCatalogoCpms />
      <SeccionCatalogoGtin />
    </div>
  );
}
