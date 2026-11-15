import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ProductoCatalogo = components["schemas"]["ProductoCatalogoRespuesta"];
export type SolicitudProductoDispensado = components["schemas"]["SolicitudProductoDispensado"];
export type ProductoRegistrado = components["schemas"]["ProductoRegistradoRespuesta"];
export type VersionCatalogoGtin = components["schemas"]["VersionCatalogoGtinRespuesta"];

export function buscar_productos_catalogo(buscar: string): Promise<ProductoCatalogo[]> {
  return obtener<ProductoCatalogo[]>("/catalogo-gtin/productos", { buscar });
}

export function registrar_producto(
  cuenta_id: number,
  datos: SolicitudProductoDispensado,
): Promise<ProductoRegistrado> {
  return enviar<ProductoRegistrado>("POST", `/cuentas/${cuenta_id}/productos`, datos);
}

export function quitar_producto(cuenta_id: number, producto_id: number): Promise<void> {
  return enviar<void>("DELETE", `/cuentas/${cuenta_id}/productos/${producto_id}`);
}

export function listar_versiones_gtin(): Promise<VersionCatalogoGtin[]> {
  return obtener<VersionCatalogoGtin[]>("/catalogo-gtin/versiones");
}

export function cargar_catalogo_gtin(): Promise<VersionCatalogoGtin> {
  return enviar<VersionCatalogoGtin>("POST", "/catalogo-gtin/versiones");
}

export function listar_productos_version_gtin(version_id: number): Promise<ProductoCatalogo[]> {
  return obtener<ProductoCatalogo[]>(`/catalogo-gtin/versiones/${version_id}/productos`);
}
