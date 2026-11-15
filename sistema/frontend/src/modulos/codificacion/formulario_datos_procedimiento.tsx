import { CampoTexto } from "../../componentes_base/campo_texto";
import type { DatosConfirmacion } from "./tipos_confirmacion";

interface Propiedades {
  datos: DatosConfirmacion;
  al_cambiar: (datos: DatosConfirmacion) => void;
}

export function FormularioDatosProcedimiento({ datos, al_cambiar }: Propiedades) {
  return (
    <>
      <CampoTexto
        etiqueta="Cantidad"
        type="number"
        min={1}
        value={datos.cantidad}
        onChange={(evento) => al_cambiar({ ...datos, cantidad: evento.target.value })}
      />
      <CampoTexto
        etiqueta="Monto unitario (S/)"
        type="number"
        step="0.01"
        value={datos.monto_unitario}
        onChange={(evento) => al_cambiar({ ...datos, monto_unitario: evento.target.value })}
      />
      <CampoTexto
        etiqueta="Fecha"
        type="date"
        value={datos.fecha}
        onChange={(evento) => al_cambiar({ ...datos, fecha: evento.target.value })}
      />
    </>
  );
}
