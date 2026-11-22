import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  consultar_conformidad_auditoria,
  registrar_conformidad_auditoria,
} from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { RegistroManual } from "../../componentes_base/registro_manual";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";

// CU-07 y CU-08: el resultado de la auditoria de la IAFAS llega mientras
// la cuenta esta EN_AUDITORIA (o SUBSANADA, si la IAFAS vuelve a auditar):
// una observacion (CU-08) o la conformidad sin observaciones (CU-07).
const _ESTADOS_CON_AUDITORIA = new Set(["EN_AUDITORIA", "SUBSANADA"]);

function DialogoConformidad({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: () => registrar_conformidad_auditoria(cuenta_id),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      await cliente_consultas.invalidateQueries({ queryKey: ["plazos"] });
      await cliente_consultas.invalidateQueries({ queryKey: ["avisos"] });
      al_cerrar();
    },
  });
  return (
    <Dialogo
      titulo="Conformidad de la auditoría de la IAFAS"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending}
          >
            Registrar conformidad
          </Boton>
        </>
      }
    >
      <p>Resultado de la auditoría: sin observaciones.</p>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar la conformidad."
      />
    </Dialogo>
  );
}

interface Propiedades {
  cuenta_id: number;
  estado: string;
  puede_registrar: boolean;
  al_registrar_observacion: () => void;
}

export function ResultadoAuditoria(propiedades: Propiedades) {
  const { cuenta_id, estado, puede_registrar, al_registrar_observacion } = propiedades;
  const en_auditoria = _ESTADOS_CON_AUDITORIA.has(estado);
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "auditoria"],
    queryFn: () => consultar_conformidad_auditoria(cuenta_id),
    enabled: en_auditoria,
  });
  const [confirmar, set_confirmar] = useState(false);

  if (!en_auditoria) return null;
  const conforme_en = consulta.data?.conforme_en ?? null;
  if (conforme_en) {
    return (
      <div className={estilos.fila_accion}>
        <span className={estilos.etiqueta_dato}>Auditoría conforme</span>
        <span>{formatear_fecha_hora(conforme_en)}</span>
      </div>
    );
  }
  if (!puede_registrar || consulta.isPending) return null;
  return (
    <div className={estilos.fila_accion}>
      <RegistroManual rotulo="Registrar observación o conformidad">
        <Boton variante="secundario" onClick={al_registrar_observacion}>
          Registrar observación de la IAFAS
        </Boton>
        <Boton variante="secundario" onClick={() => set_confirmar(true)}>
          Registrar conformidad de la IAFAS
        </Boton>
      </RegistroManual>
      {confirmar ? (
        <DialogoConformidad cuenta_id={cuenta_id} al_cerrar={() => set_confirmar(false)} />
      ) : null}
    </div>
  );
}
