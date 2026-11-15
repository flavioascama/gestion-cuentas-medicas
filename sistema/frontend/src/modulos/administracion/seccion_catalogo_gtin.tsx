import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cargar_catalogo_gtin,
  listar_productos_version_gtin,
  listar_versiones_gtin,
  type ProductoCatalogo,
  type VersionCatalogoGtin,
} from "../../api/farmacia";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "./administracion.module.css";

// CU-18: versiones del catalogo GTIN (nunca se modifican; cada carga es una
// version nueva) y los productos de la vigente.
const _COLUMNAS_VERSIONES: ColumnaTabla<VersionCatalogoGtin>[] = [
  { clave: "id", encabezado: "Versión", alinear_centro: true },
  { clave: "conteo", encabezado: "Productos", alinear_derecha: true },
  {
    clave: "cargado_en",
    encabezado: "Cargado",
    formatear: (fila) => formatear_fecha_hora(fila.cargado_en),
  },
];

const _COLUMNAS_PRODUCTOS: ColumnaTabla<ProductoCatalogo>[] = [
  { clave: "codigo", encabezado: "GTIN" },
  { clave: "nombre", encabezado: "Nombre" },
  { clave: "denominacion_comun", encabezado: "Denominación común" },
  { clave: "concentracion", encabezado: "Concentración", formatear: (f) => f.concentracion ?? "—" },
  { clave: "tipo_producto_tedef", encabezado: "Tipo", alinear_centro: true },
];

export function SeccionCatalogoGtin() {
  const cliente_consultas = useQueryClient();
  const versiones = useQuery({
    queryKey: ["administracion", "gtin"],
    queryFn: listar_versiones_gtin,
  });
  const vigente = versiones.data?.[0]?.id;
  const productos = useQuery({
    queryKey: ["administracion", "gtin", vigente, "productos"],
    queryFn: () => listar_productos_version_gtin(vigente ?? 0),
    enabled: vigente !== undefined,
  });
  const cargar = useMutation({
    mutationFn: cargar_catalogo_gtin,
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({ queryKey: ["administracion", "gtin"] }),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Catálogo GTIN</div>
      <MensajeErrorMutacion
        error={cargar.error}
        texto_por_defecto="No se pudo cargar el catálogo."
      />
      <Boton variante="secundario" onClick={() => cargar.mutate()} disabled={cargar.isPending}>
        Cargar nueva versión
      </Boton>
      <TablaDatos
        columnas={_COLUMNAS_VERSIONES}
        filas={versiones.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={versiones.isPending}
        error={versiones.error}
        mensaje_vacio="No hay versiones del catálogo GTIN cargadas."
      />
      {vigente !== undefined ? (
        <TablaDatos
          columnas={_COLUMNAS_PRODUCTOS}
          filas={productos.data ?? []}
          obtener_clave={(fila) => fila.codigo}
          cargando={productos.isPending}
          error={productos.error}
          mensaje_vacio="La versión vigente no tiene productos."
        />
      ) : null}
    </div>
  );
}
