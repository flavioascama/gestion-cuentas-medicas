import { Boton } from "../../componentes_base/boton";
import type { DatosConfirmacion } from "./tipos_confirmacion";

// La regla del servidor: cantidad entera mayor que cero y monto mayor que cero.
function datos_validos(datos: DatosConfirmacion): boolean {
  return /^[1-9]\d*$/.test(datos.cantidad) && Number(datos.monto_unitario) > 0;
}

interface Propiedades {
  datos: DatosConfirmacion;
  confirmando: boolean;
  al_cerrar: () => void;
  al_confirmar: () => void;
}

export function AccionesConfirmarProcedimiento({
  datos,
  confirmando,
  al_cerrar,
  al_confirmar,
}: Propiedades) {
  return (
    <>
      <Boton variante="secundario" onClick={al_cerrar}>
        Cancelar
      </Boton>
      <Boton
        variante="primario"
        onClick={al_confirmar}
        disabled={confirmando || !datos_validos(datos) || !datos.fecha}
      >
        Confirmar
      </Boton>
    </>
  );
}
