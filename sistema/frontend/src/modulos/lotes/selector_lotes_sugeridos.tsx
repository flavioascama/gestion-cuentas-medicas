import type { LoteSugerido } from "../../api/lotes";
import { formatear_monto, formatear_periodo } from "../../utilidades/formato";
import { clave_lote_sugerido } from "./usar_formulario_generar_lote";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  sugeridos: LoteSugerido[];
  elegido: LoteSugerido | undefined;
  al_elegir: (clave: string) => void;
}

function texto_cantidad(cantidad: number): string {
  return cantidad === 1 ? "1 cuenta" : `${cantidad} cuentas`;
}

export function SelectorLotesSugeridos({ sugeridos, elegido, al_elegir }: Propiedades) {
  const clave_elegida = elegido ? clave_lote_sugerido(elegido) : null;
  return (
    <fieldset className={estilos.grupo}>
      <legend className={estilos.leyenda}>Lotes sugeridos</legend>
      <div className={estilos.lista_sugeridos}>
        {sugeridos.map((sugerido) => {
          const clave = clave_lote_sugerido(sugerido);
          const marcado = clave === clave_elegida;
          return (
            <label
              key={clave}
              className={`${estilos.fila_sugerido} ${marcado ? estilos.fila_elegida : ""}`}
            >
              <input
                type="radio"
                name="lote_sugerido"
                checked={marcado}
                onChange={() => al_elegir(clave)}
              />
              <span className={estilos.texto_largo}>
                {sugerido.iafas_codigo} — {sugerido.iafas_razon_social}
              </span>
              <span>{formatear_periodo(sugerido.periodo)}</span>
              <span className={estilos.dato_numerico}>
                {texto_cantidad(sugerido.cuentas.length)}
              </span>
              <span className={estilos.dato_numerico}>{formatear_monto(sugerido.monto_total)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
