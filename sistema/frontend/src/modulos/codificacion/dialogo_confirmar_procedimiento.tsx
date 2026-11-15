import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  confirmar_procedimiento,
  type CandidatoCpms,
  type SolicitudConfirmarProcedimiento,
} from "../../api/cpms";
import { ErrorApi } from "../../api/cliente_http";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { AccionesConfirmarProcedimiento } from "./acciones_confirmar_procedimiento";
import { FormularioDatosProcedimiento } from "./formulario_datos_procedimiento";
import { DATOS_CONFIRMACION_INICIALES, type DatosConfirmacion } from "./tipos_confirmacion";
import estilos from "./asistente_cpms.module.css";

interface Propiedades {
  candidato: CandidatoCpms;
  cuenta_id: number;
  inicio_sugerencia: string;
  descripcion: string;
  al_cerrar: () => void;
  al_confirmar: () => void;
}

function construir_solicitud(
  candidato: CandidatoCpms,
  descripcion: string,
  datos: DatosConfirmacion,
  inicio_sugerencia: string,
): SolicitudConfirmarProcedimiento {
  return {
    descripcion_registrada: descripcion,
    codigo_elegido: candidato.codigo,
    posicion_aceptada: candidato.posicion,
    cantidad: Number(datos.cantidad),
    monto_unitario: datos.monto_unitario,
    fecha: datos.fecha,
    inicio_sugerencia,
  };
}

function usar_confirmar_procedimiento(propiedades: Propiedades, datos: DatosConfirmacion) {
  const { cuenta_id, candidato, descripcion, inicio_sugerencia, al_confirmar } = propiedades;
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () =>
      confirmar_procedimiento(
        cuenta_id,
        construir_solicitud(candidato, descripcion, datos, inicio_sugerencia),
      ),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({
        queryKey: ["cuentas", cuenta_id, "completitud"],
      });
      // Tambien la cuenta base, no solo la completitud: la tabla de
      // "Procedimientos" del detalle de cuenta (ListasCuenta) lee
      // cuenta.procedimientos de esa misma consulta, y sin esto se queda
      // mostrando la lista vieja hasta que algo mas la invalide.
      void cliente_consultas.invalidateQueries({
        queryKey: ["cuentas", cuenta_id],
        exact: true,
      });
      al_confirmar();
    },
  });
}

export function DialogoConfirmarProcedimiento(propiedades: Propiedades) {
  const { candidato, al_cerrar } = propiedades;
  const [datos, set_datos] = useState(DATOS_CONFIRMACION_INICIALES);
  const mutacion = usar_confirmar_procedimiento(propiedades, datos);

  return (
    <Dialogo
      titulo={`Confirmar código ${candidato.codigo}`}
      al_cerrar={al_cerrar}
      acciones={
        <AccionesConfirmarProcedimiento
          datos={datos}
          confirmando={mutacion.isPending}
          al_cerrar={al_cerrar}
          al_confirmar={() => mutacion.mutate()}
        />
      }
    >
      <div className={estilos.formulario_confirmacion}>
        <p>{candidato.denominacion}</p>
        {mutacion.isError ? (
          <Mensaje
            tipo="error"
            texto={
              mutacion.error instanceof ErrorApi ? mutacion.error.message : "No se pudo confirmar."
            }
          />
        ) : null}
        <FormularioDatosProcedimiento datos={datos} al_cambiar={set_datos} />
      </div>
    </Dialogo>
  );
}
