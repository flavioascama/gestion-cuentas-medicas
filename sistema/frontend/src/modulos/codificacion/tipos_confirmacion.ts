export interface DatosConfirmacion {
  cantidad: string;
  monto_unitario: string;
  fecha: string;
}

export const DATOS_CONFIRMACION_INICIALES: DatosConfirmacion = {
  cantidad: "1",
  monto_unitario: "",
  fecha: "",
};
