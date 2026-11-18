import { usar_sesion } from "../../sesion/contexto_sesion";
import {
  tiene_acceso_observaciones,
  usar_descripciones_motivos,
} from "../observaciones/usar_observaciones";
import { crear_columnas_comunicaciones } from "./columnas_comunicaciones";

// Las columnas de una tabla de comunicaciones, con la descripcion de cada
// motivo de observacion para quien puede ver ese catalogo.
export function usar_columnas_comunicaciones() {
  const { sesion } = usar_sesion();
  const motivos = usar_descripciones_motivos(tiene_acceso_observaciones(sesion));
  return crear_columnas_comunicaciones(motivos);
}
