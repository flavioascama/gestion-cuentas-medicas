import { Mensaje } from "../../componentes_base/mensaje";
import { TablaDatos } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { COLUMNAS_HISTORIAL } from "./columnas_historial";
import { tiene_acceso_historial, usar_historial_lote } from "./usar_trazabilidad";

// RT-13: el historial de cualquier lote, con las mismas columnas y la
// misma verificacion de la cadena que el de la cuenta.
export function SeccionHistorialLote({ lote_id }: { lote_id: number }) {
  const { sesion } = usar_sesion();
  const acceso = tiene_acceso_historial(sesion);
  const consulta = usar_historial_lote(lote_id, acceso);

  if (!acceso) return null;
  const historial = consulta.data;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Historial del lote</div>
      {historial && !historial.cadena_integra ? (
        <Mensaje
          tipo="error"
          texto={`Se detectó una ruptura en la cadena de eventos: ${historial.rupturas.join("; ")}`}
        />
      ) : null}
      <TablaDatos
        columnas={COLUMNAS_HISTORIAL}
        filas={historial?.eventos ?? []}
        obtener_clave={(_fila, indice) => indice}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="El lote no tiene eventos registrados."
      />
    </div>
  );
}
