import { useState } from "react";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { TablaDatos } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { COLUMNAS_HISTORIAL } from "./columnas_historial";
import { DialogoExportarExpediente } from "./dialogo_exportar_expediente";
import { tiene_acceso_historial, usar_historial_cuenta } from "./usar_trazabilidad";

export function SeccionHistorial({ cuenta_id }: { cuenta_id: number }) {
  const { sesion } = usar_sesion();
  const consulta = usar_historial_cuenta(cuenta_id);
  const [mostrar_expediente, set_mostrar_expediente] = useState(false);

  if (!tiene_acceso_historial(sesion)) return null;

  const historial = consulta.data;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Historial de la cuenta</div>
      <div className={estilos.fila_accion}>
        <Boton variante="secundario" onClick={() => set_mostrar_expediente(true)}>
          Exportar expediente de auditoría
        </Boton>
      </div>
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
        mensaje_vacio="La cuenta no tiene eventos registrados."
      />
      {mostrar_expediente ? (
        <DialogoExportarExpediente
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_expediente(false)}
        />
      ) : null}
    </div>
  );
}
