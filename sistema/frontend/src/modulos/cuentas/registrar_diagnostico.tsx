import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { registrar_diagnostico } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { CampoCie10 } from "./campo_cie10";
import estilos from "./detalle_cuenta.module.css";

// El diagnostico principal es opcional al registrar la cuenta, pero el lote
// lo exige: aqui se completa despues (2026-11-18). Antes no habia forma, y
// una cuenta sin diagnostico quedaba facturada sin poder entrar a un lote.
export function RegistrarDiagnostico({ cuenta_id }: { cuenta_id: number }) {
  const cliente_consultas = useQueryClient();
  const [codigo, set_codigo] = useState("");
  const mutacion = useMutation({
    mutationFn: () => registrar_diagnostico(cuenta_id, codigo),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] }),
  });

  return (
    <div className={estilos.formulario_en_paso}>
      <CampoCie10
        value={codigo}
        onChange={set_codigo}
        etiqueta="Diagnóstico principal (CIE-10)"
        obligatorio
      />
      <div className={estilos.fila_accion}>
        <Boton
          variante="primario"
          onClick={() => mutacion.mutate()}
          disabled={mutacion.isPending || !codigo}
        >
          Guardar diagnóstico
        </Boton>
      </div>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo guardar el diagnóstico."
      />
    </div>
  );
}
