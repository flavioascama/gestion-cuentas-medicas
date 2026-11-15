import { useMutation } from "@tanstack/react-query";
import { registrar_cuenta } from "../../api/cuentas";
import { FormularioNuevaCuenta } from "./formulario_nueva_cuenta";
import { usar_formulario_nueva_cuenta } from "./usar_formulario_nueva_cuenta";

interface Propiedades {
  al_cerrar: () => void;
  al_registrar: (cuenta_id: number) => void;
}

export function DialogoNuevaCuenta({ al_cerrar, al_registrar }: Propiedades) {
  const formulario = usar_formulario_nueva_cuenta();

  const mutacion = useMutation({
    mutationFn: () => registrar_cuenta(formulario.a_solicitud()),
    onSuccess: (respuesta) => al_registrar(respuesta.cuenta_id),
  });

  return (
    <FormularioNuevaCuenta
      formulario={formulario}
      registrando={mutacion.isPending}
      error={mutacion.error}
      al_registrar={() => mutacion.mutate()}
      al_cerrar={al_cerrar}
    />
  );
}
