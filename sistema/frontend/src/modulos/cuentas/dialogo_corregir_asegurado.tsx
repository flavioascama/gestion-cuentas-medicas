import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { corregir_asegurado, type SolicitudCorregirAsegurado } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";

interface Propiedades {
  cuenta_id: number;
  nombres: string;
  apellidos: string;
  al_cerrar: () => void;
}

function usar_corregir_asegurado(
  cuenta_id: number,
  datos: SolicitudCorregirAsegurado,
  al_cerrar: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () =>
      corregir_asegurado(cuenta_id, {
        nombres_asegurado: datos.nombres_asegurado.trim(),
        apellidos_asegurado: datos.apellidos_asegurado.trim(),
      }),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas"] });
      al_cerrar();
    },
  });
}

function CampoNombre(props: { etiqueta: string; valor: string; cambiar: (v: string) => void }) {
  return (
    <CampoTexto
      etiqueta={props.etiqueta}
      obligatorio
      maxLength={150}
      value={props.valor}
      onChange={(evento) => props.cambiar(evento.target.value)}
    />
  );
}

// Corrige nombres y apellidos del asegurado mientras la cuenta esta
// registrada (igual que el servidor). El documento no se corrige.
export function DialogoCorregirAsegurado({
  cuenta_id,
  nombres,
  apellidos,
  al_cerrar,
}: Propiedades) {
  const [nombres_asegurado, set_nombres] = useState(nombres);
  const [apellidos_asegurado, set_apellidos] = useState(apellidos);
  const mutacion = usar_corregir_asegurado(
    cuenta_id,
    { nombres_asegurado, apellidos_asegurado },
    al_cerrar,
  );
  const completo = nombres_asegurado.trim() !== "" && apellidos_asegurado.trim() !== "";

  return (
    <Dialogo
      titulo="Corregir asegurado"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={!completo || mutacion.isPending}
          >
            Guardar corrección
          </Boton>
        </>
      }
    >
      <CampoNombre
        etiqueta="Nombres del asegurado"
        valor={nombres_asegurado}
        cambiar={set_nombres}
      />
      <CampoNombre
        etiqueta="Apellidos del asegurado"
        valor={apellidos_asegurado}
        cambiar={set_apellidos}
      />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo corregir el asegurado."
      />
    </Dialogo>
  );
}
