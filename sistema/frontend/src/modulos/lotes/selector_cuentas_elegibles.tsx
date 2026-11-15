import type { ResumenCuenta } from "../../api/cuentas";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  codigo_iafas: string;
  cuentas: ResumenCuenta[];
  cuenta_ids_elegidos: number[];
  al_alternar: (cuenta_id: number) => void;
}

export function SelectorCuentasElegibles({
  codigo_iafas,
  cuentas,
  cuenta_ids_elegidos,
  al_alternar,
}: Propiedades) {
  return (
    <div>
      <label>Cuentas facturadas de {codigo_iafas}</label>
      <div className={estilos.lista_cuentas}>
        {cuentas.length === 0 ? (
          <p>No hay cuentas facturadas para esta IAFAS.</p>
        ) : (
          cuentas.map((cuenta) => (
            <div key={cuenta.id} className={estilos.fila_cuenta}>
              <input
                type="checkbox"
                id={`cuenta_${cuenta.id}`}
                checked={cuenta_ids_elegidos.includes(cuenta.id)}
                onChange={() => al_alternar(cuenta.id)}
              />
              <label htmlFor={`cuenta_${cuenta.id}`}>
                {cuenta.identificacion_interna} — {cuenta.nombres_asegurado}{" "}
                {cuenta.apellidos_asegurado}
              </label>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
