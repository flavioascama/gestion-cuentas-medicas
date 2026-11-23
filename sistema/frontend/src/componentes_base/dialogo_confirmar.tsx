import { useState, type ReactNode } from "react";
import { Boton } from "./boton";
import { Dialogo } from "./dialogo";

interface Propiedades {
  titulo: string;
  texto: string;
  texto_confirmar: string;
  al_confirmar: () => void;
  al_cerrar: () => void;
}

// Confirmacion antes de una accion que no se puede deshacer.
export function DialogoConfirmar(propiedades: Propiedades) {
  const { al_cerrar } = propiedades;
  return (
    <Dialogo
      titulo={propiedades.titulo}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => {
              propiedades.al_confirmar();
              al_cerrar();
            }}
          >
            {propiedades.texto_confirmar}
          </Boton>
        </>
      }
    >
      <p>{propiedades.texto}</p>
    </Dialogo>
  );
}

interface PropiedadesBoton {
  variante: "primario" | "secundario" | "terciario";
  disabled?: boolean;
  titulo: string;
  texto: string;
  texto_confirmar: string;
  al_confirmar: () => void;
  children: ReactNode;
}

// Un boton que pide confirmacion antes de ejecutar su accion.
export function BotonConConfirmacion(propiedades: PropiedadesBoton) {
  const [confirmando, set_confirmando] = useState(false);
  return (
    <>
      <Boton
        variante={propiedades.variante}
        onClick={() => set_confirmando(true)}
        disabled={propiedades.disabled}
      >
        {propiedades.children}
      </Boton>
      {confirmando ? (
        <DialogoConfirmar
          titulo={propiedades.titulo}
          texto={propiedades.texto}
          texto_confirmar={propiedades.texto_confirmar}
          al_confirmar={propiedades.al_confirmar}
          al_cerrar={() => set_confirmando(false)}
        />
      ) : null}
    </>
  );
}
