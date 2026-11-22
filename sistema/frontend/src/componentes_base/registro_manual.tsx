import { useState, type ReactNode } from "react";
import { Boton } from "./boton";

// Lo que la IAFAS comunica por su portal o por correo se registra solo
// (2026-11-18). El registro a mano queda como opcion secundaria, para lo que
// llegue por otro medio: se muestra recien cuando la persona lo pide.
// El rotulo dice que se registra ("Registrar liquidación", etc.).
export function RegistroManual({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  const [abierto, set_abierto] = useState(false);
  if (!abierto) {
    return (
      <Boton variante="terciario" onClick={() => set_abierto(true)}>
        {rotulo}
      </Boton>
    );
  }
  return <>{children}</>;
}
