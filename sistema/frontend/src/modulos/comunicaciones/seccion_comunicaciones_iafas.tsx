import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  listar_comunicaciones_iafas,
  solicitar_revision_comunicaciones,
  type ComunicacionIafas,
} from "../../api/comunicaciones_iafas";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { TablaDatos } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { columna_ver, crear_columnas_comunicaciones } from "./columnas_comunicaciones";
import { DialogoComunicacion } from "./dialogo_comunicacion";
import { TablaCorreos } from "./tabla_correos";

const _REVISA = ["analista", "jefe", "tesoreria"];

export function AccionRevisar() {
  const { sesion } = usar_sesion();
  const cliente = useQueryClient();
  const revision = useMutation({ mutationFn: solicitar_revision_comunicaciones });
  const al_completar = useCallback(() => void cliente.invalidateQueries(), [cliente]);

  if (!sesion?.roles.some((rol) => _REVISA.includes(rol))) return null;
  return (
    <div className={estilos.fila_accion}>
      <Boton variante="secundario" onClick={() => revision.mutate()} disabled={revision.isPending}>
        Revisar portal y correo de la IAFAS
      </Boton>
      {revision.data ? (
        <ProgresoTrabajo trabajo_id={revision.data.trabajo_id} al_completar={al_completar} />
      ) : null}
      <MensajeErrorMutacion
        error={revision.error}
        texto_por_defecto="No se pudo solicitar la revisión."
      />
    </div>
  );
}

export function SeccionComunicacionesIafas({ cuenta_id }: { cuenta_id: number }) {
  const [abierta, set_abierta] = useState<ComunicacionIafas | null>(null);
  const columnas = [...crear_columnas_comunicaciones(), columna_ver(set_abierta)];
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comunicaciones_iafas"],
    queryFn: () => listar_comunicaciones_iafas(cuenta_id),
  });

  return (
    <>
      <div className={estilos.seccion}>
        <div className={estilos.titulo_seccion}>Comunicaciones de la IAFAS</div>
        <AccionRevisar />
        <TablaDatos
          columnas={columnas}
          filas={consulta.data ?? []}
          obtener_clave={(fila) => fila.codigo}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="Sin comunicaciones de la IAFAS para esta cuenta."
        />
        {abierta !== null ? (
          <DialogoComunicacion comunicacion={abierta} al_cerrar={() => set_abierta(null)} />
        ) : null}
      </div>
      <div className={estilos.seccion}>
        <div className={estilos.titulo_seccion}>Correos recibidos</div>
        <TablaCorreos
          filtro={{ cuenta_id }}
          mostrar_cuenta={false}
          mensaje_vacio="Sin correos de esta cuenta."
        />
      </div>
    </>
  );
}
