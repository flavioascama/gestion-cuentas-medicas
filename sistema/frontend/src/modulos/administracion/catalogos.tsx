import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cargar_catalogo_cpms, type VersionCpms } from "../../api/cpms";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { SeccionCatalogoGtin } from "./seccion_catalogo_gtin";
import { usar_versiones_cpms } from "./usar_administracion";
import estilos from "./administracion.module.css";

// CU-18: catalogos versionados (procedimientos CPMS y productos GTIN) en su
// propia pantalla (rediseno de la administracion, 2026-11-15).
const _COLUMNAS_CPMS: ColumnaTabla<VersionCpms>[] = [
  { clave: "etiqueta", encabezado: "Versión" },
  { clave: "conteo", encabezado: "Procedimientos", alinear_derecha: true },
  {
    clave: "creado_en",
    encabezado: "Cargada",
    formatear: (fila) => formatear_fecha_hora(fila.creado_en),
  },
];

function SeccionCatalogoCpms() {
  const cliente_consultas = useQueryClient();
  const consulta = usar_versiones_cpms();
  const cargar = useMutation({
    mutationFn: () => cargar_catalogo_cpms(),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({ queryKey: ["administracion", "cpms"] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.cabecera_seccion}>
        <div className={estilos.titulo_seccion}>Procedimientos médicos (CPMS)</div>
        <Boton variante="secundario" onClick={() => cargar.mutate()} disabled={cargar.isPending}>
          Cargar nueva versión
        </Boton>
      </div>
      <MensajeErrorMutacion
        error={cargar.error}
        texto_por_defecto="No se pudo cargar el catálogo."
      />
      <TablaDatos
        columnas={_COLUMNAS_CPMS}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay versiones del catálogo de procedimientos."
      />
    </div>
  );
}

export function AdministracionCatalogos() {
  return (
    <div>
      <TituloPagina titulo="Catálogos" />
      <SeccionCatalogoCpms />
      <SeccionCatalogoGtin />
    </div>
  );
}
