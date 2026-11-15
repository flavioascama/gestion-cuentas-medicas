import { useState } from "react";
import { Boton } from "../../componentes_base/boton";
import { usar_sesion } from "../../sesion/contexto_sesion";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { es_visible_cierre_anulacion } from "./usar_cierre";
import { DialogoConfirmarCierre } from "./dialogo_confirmar_cierre";
import { DialogoSolicitarAnulacion } from "./dialogo_solicitar_anulacion";

const _ESTADOS_CIERRE = new Set(["PAGADA", "PAGADA_PARCIAL"]);

export function SeccionCierreAnulacion({
  cuenta_id,
  estado,
}: {
  cuenta_id: number;
  estado: string;
}) {
  const { sesion } = usar_sesion();
  const [mostrar_cierre, set_mostrar_cierre] = useState(false);
  const [mostrar_anulacion, set_mostrar_anulacion] = useState(false);

  if (!es_visible_cierre_anulacion(sesion, estado)) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Cierre y anulación</div>
      <div className={estilos.fila_accion}>
        {_ESTADOS_CIERRE.has(estado) ? (
          <Boton variante="secundario" onClick={() => set_mostrar_cierre(true)}>
            Cerrar cuenta
          </Boton>
        ) : null}
        <Boton variante="destructivo" onClick={() => set_mostrar_anulacion(true)}>
          Solicitar anulación
        </Boton>
      </div>
      {mostrar_cierre ? (
        <DialogoConfirmarCierre
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_cierre(false)}
          al_confirmar={() => set_mostrar_cierre(false)}
        />
      ) : null}
      {mostrar_anulacion ? (
        <DialogoSolicitarAnulacion
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_anulacion(false)}
          al_solicitar={() => set_mostrar_anulacion(false)}
        />
      ) : null}
    </div>
  );
}
