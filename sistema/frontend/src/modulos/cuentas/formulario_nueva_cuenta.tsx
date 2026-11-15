import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { CamposNuevaCuenta } from "./campos_nueva_cuenta";
import type { usar_formulario_nueva_cuenta } from "./usar_formulario_nueva_cuenta";
import estilos from "./dialogo_nueva_cuenta.module.css";

interface Propiedades {
  formulario: ReturnType<typeof usar_formulario_nueva_cuenta>;
  registrando: boolean;
  error: unknown;
  al_registrar: () => void;
  al_cerrar: () => void;
}

export function FormularioNuevaCuenta({
  formulario,
  registrando,
  error,
  al_registrar,
  al_cerrar,
}: Propiedades) {
  return (
    <Dialogo
      titulo="Nueva cuenta médica"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={al_registrar}
            disabled={registrando || formulario.falta_completar}
          >
            Registrar
          </Boton>
        </>
      }
    >
      <div className={estilos.formulario}>
        <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo registrar la cuenta." />
        <CamposNuevaCuenta formulario={formulario} />
      </div>
    </Dialogo>
  );
}
