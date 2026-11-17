import type { CuentaPorLotear } from "../../api/lotes";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  cuentas: CuentaPorLotear[];
  excluidas: number[];
  al_alternar: (cuenta_id: number) => void;
  al_alternar_todas: () => void;
}

// Todas las cuentas del grupo vienen marcadas: el analista solo desmarca
// las que no deben entrar en este lote.
export function SelectorCuentasElegibles({
  cuentas,
  excluidas,
  al_alternar,
  al_alternar_todas,
}: Propiedades) {
  const marcadas = cuentas.filter((cuenta) => !excluidas.includes(cuenta.cuenta_id)).length;
  return (
    <fieldset className={estilos.grupo}>
      <legend className={estilos.leyenda}>
        Cuentas del lote ({marcadas} de {cuentas.length})
      </legend>
      <div className={estilos.lista_cuentas}>
        <label className={`${estilos.fila_cuenta} ${estilos.fila_todas}`}>
          <input
            type="checkbox"
            checked={marcadas === cuentas.length}
            onChange={al_alternar_todas}
          />
          <span>Todas</span>
        </label>
        {cuentas.map((cuenta) => (
          <label key={cuenta.cuenta_id} className={estilos.fila_cuenta}>
            <input
              type="checkbox"
              checked={!excluidas.includes(cuenta.cuenta_id)}
              onChange={() => al_alternar(cuenta.cuenta_id)}
            />
            <span className={estilos.texto_largo}>
              {cuenta.identificacion_interna} — {cuenta.nombres_asegurado}{" "}
              {cuenta.apellidos_asegurado}
            </span>
            <span>{formatear_fecha(cuenta.fecha_emision)}</span>
            <span className={estilos.dato_numerico}>{formatear_monto(cuenta.monto)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
