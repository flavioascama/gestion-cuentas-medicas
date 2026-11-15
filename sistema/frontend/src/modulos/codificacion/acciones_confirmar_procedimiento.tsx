import { Boton } from "../../componentes_base/boton";
import type { DatosConfirmacion } from "./tipos_confirmacion";

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
        disabled={confirmando || !datos.cantidad || !datos.monto_unitario || !datos.fecha}
      >
        Confirmar
      </Boton>
    </>
  );
}
