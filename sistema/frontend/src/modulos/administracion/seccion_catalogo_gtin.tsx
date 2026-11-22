import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cargar_catalogo_gtin,
  listar_productos_version_gtin,
  listar_versiones_gtin,
  type ProductoCatalogo,
  type VersionCatalogoGtin,
} from "../../api/farmacia";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { etiqueta_tipo_producto } from "../../componentes_base/mapa_tipos_producto";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { leer_base64 } from "../../utilidades/archivo";
import { formatear_fecha, formatear_fecha_hora } from "../../utilidades/formato";
import { BotonCargarCatalogo } from "./boton_cargar_catalogo";
import { formatear_cantidad } from "./formato_administracion";
import estilos from "./administracion.module.css";

// CU-18: versiones del catalogo GTIN (nunca se modifican; cada carga es una
// version nueva) y los productos de la vigente.
function columnas_versiones(vigente: number | undefined): ColumnaTabla<VersionCatalogoGtin>[] {
  return [
    {
      clave: "id",
      encabezado: "Versión",
      formatear: (fila) => {
        const fecha = formatear_fecha(fila.cargado_en);
        return fila.id === vigente ? `${fecha} (vigente)` : fecha;
      },
    },
    {
      clave: "conteo",
      encabezado: "Productos",
      formatear: (fila) => formatear_cantidad(fila.conteo),
    },
    {
      clave: "cargado_en",
      encabezado: "Cargada",
      formatear: (fila) => formatear_fecha_hora(fila.cargado_en),
    },
  ];
}

const _COLUMNAS_PRODUCTOS: ColumnaTabla<ProductoCatalogo>[] = [
  { clave: "codigo", encabezado: "Código GTIN" },
  { clave: "nombre", encabezado: "Nombre" },
  { clave: "denominacion_comun", encabezado: "Denominación común" },
  { clave: "concentracion", encabezado: "Concentración", formatear: (f) => f.concentracion ?? "—" },
  {
    clave: "tipo_producto_tedef",
    encabezado: "Tipo",
    formatear: (f) => etiqueta_tipo_producto(f.tipo_producto_tedef),
  },
];

function coincide(producto: ProductoCatalogo, busqueda: string): boolean {
  const texto = busqueda.trim().toLowerCase();
  if (!texto) return true;
  return [producto.codigo, producto.nombre, producto.denominacion_comun].some((valor) =>
    valor.toLowerCase().includes(texto),
  );
}

function ProductosVigentes({ version_id }: { version_id: number }) {
  const [busqueda, set_busqueda] = useState("");
  const productos = useQuery({
    queryKey: ["administracion", "gtin", version_id, "productos"],
    queryFn: () => listar_productos_version_gtin(version_id),
  });
  const filtrados = (productos.data ?? []).filter((producto) => coincide(producto, busqueda));
  return (
    <>
      <div className={estilos.subtitulo}>Productos de la versión vigente</div>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => set_busqueda(evento.target.value)}
          placeholder="Código o nombre"
        />
      </div>
      <TablaDatos
        columnas={_COLUMNAS_PRODUCTOS}
        filas={filtrados}
        obtener_clave={(fila) => fila.codigo}
        cargando={productos.isPending}
        error={productos.error}
        mensaje_vacio={
          busqueda
            ? "Ningún producto coincide con la búsqueda."
            : "La versión vigente no tiene productos."
        }
      />
    </>
  );
}

export function SeccionCatalogoGtin() {
  const cliente_consultas = useQueryClient();
  const versiones = useQuery({
    queryKey: ["administracion", "gtin"],
    queryFn: listar_versiones_gtin,
  });
  const vigente = versiones.data?.[0]?.id;
  const cargar = useMutation({
    mutationFn: async (archivo: File) =>
      cargar_catalogo_gtin({
        nombre_archivo: archivo.name,
        contenido_base64: await leer_base64(archivo),
      }),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({ queryKey: ["administracion", "gtin"] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.cabecera_seccion}>
        <div className={estilos.titulo_seccion}>Productos farmacéuticos (GTIN)</div>
        <BotonCargarCatalogo al_elegir={cargar.mutate} disabled={cargar.isPending} />
      </div>
      <MensajeErrorMutacion
        error={cargar.error}
        texto_por_defecto="No se pudo cargar el catálogo."
      />
      {cargar.isSuccess ? (
        <Mensaje
          tipo="exito"
          texto={`Versión cargada: ${formatear_cantidad(cargar.data.conteo)} productos.`}
        />
      ) : null}
      <TablaDatos
        columnas={columnas_versiones(vigente)}
        filas={versiones.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={versiones.isPending}
        error={versiones.error}
        mensaje_vacio="No hay versiones del catálogo de productos."
      />
      {vigente !== undefined ? <ProductosVigentes version_id={vigente} /> : null}
    </div>
  );
}
