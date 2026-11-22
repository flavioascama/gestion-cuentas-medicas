import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  buscar_procedimientos_catalogo_cpms,
  cargar_catalogo_cpms,
  type ProcedimientoCatalogoCpms,
  type VersionCpms,
} from "../../api/cpms";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { leer_base64 } from "../../utilidades/archivo";
import { formatear_fecha_hora, formatear_version_catalogo } from "../../utilidades/formato";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";
import { BotonCargarCatalogo } from "./boton_cargar_catalogo";
import { formatear_cantidad } from "./formato_administracion";
import { SeccionCatalogoGtin } from "./seccion_catalogo_gtin";
import { usar_versiones_cpms } from "./usar_administracion";
import estilos from "./administracion.module.css";

// CU-18: catalogos versionados (procedimientos CPMS y productos GTIN) en su
// propia pantalla (rediseno de la administracion, 2026-11-15).

function columnas_cpms(vigente: number | undefined): ColumnaTabla<VersionCpms>[] {
  return [
    {
      clave: "etiqueta",
      encabezado: "Versión",
      formatear: (fila) => {
        const etiqueta = formatear_version_catalogo(fila.etiqueta);
        return fila.id === vigente ? `${etiqueta} (vigente)` : etiqueta;
      },
    },
    {
      clave: "conteo",
      encabezado: "Procedimientos",
      formatear: (fila) => formatear_cantidad(fila.conteo),
    },
    {
      clave: "creado_en",
      encabezado: "Cargada",
      formatear: (fila) => formatear_fecha_hora(fila.creado_en),
    },
  ];
}

const _COLUMNAS_PROCEDIMIENTOS: ColumnaTabla<ProcedimientoCatalogoCpms>[] = [
  { clave: "codigo", encabezado: "Código" },
  { clave: "nombre", encabezado: "Nombre" },
];

// Comprobar que un procedimiento esta en la version vigente.
function BuscadorProcedimientos() {
  const [busqueda, set_busqueda] = useState("");
  const texto = usar_valor_diferido(busqueda.trim());
  const resultado = useQuery({
    queryKey: ["administracion", "cpms", "procedimientos", texto],
    queryFn: () => buscar_procedimientos_catalogo_cpms(texto),
    enabled: texto !== "",
  });
  return (
    <>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => set_busqueda(evento.target.value)}
          placeholder="Código o nombre"
        />
      </div>
      {texto ? (
        <TablaDatos
          columnas={_COLUMNAS_PROCEDIMIENTOS}
          filas={resultado.data ?? []}
          obtener_clave={(fila) => fila.codigo}
          cargando={resultado.isPending}
          error={resultado.error}
          mensaje_vacio="Ningún procedimiento coincide con la búsqueda."
        />
      ) : null}
    </>
  );
}

function SeccionCatalogoCpms() {
  const cliente_consultas = useQueryClient();
  const consulta = usar_versiones_cpms();
  // La lista llega con la version mas reciente primero: esa es la vigente.
  const vigente = consulta.data?.[0]?.id;
  const cargar = useMutation({
    mutationFn: async (archivo: File) =>
      cargar_catalogo_cpms({
        nombre_archivo: archivo.name,
        contenido_base64: await leer_base64(archivo),
      }),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({ queryKey: ["administracion", "cpms"] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.cabecera_seccion}>
        <div className={estilos.titulo_seccion}>Procedimientos médicos (CPMS)</div>
        <BotonCargarCatalogo al_elegir={cargar.mutate} disabled={cargar.isPending} />
      </div>
      <MensajeErrorMutacion
        error={cargar.error}
        texto_por_defecto="No se pudo cargar el catálogo."
      />
      {cargar.isSuccess ? (
        <Mensaje
          tipo="exito"
          texto={`Versión cargada: ${formatear_cantidad(cargar.data.conteo)} procedimientos.`}
        />
      ) : null}
      <TablaDatos
        columnas={columnas_cpms(vigente)}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay versiones del catálogo de procedimientos."
      />
      <BuscadorProcedimientos />
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
