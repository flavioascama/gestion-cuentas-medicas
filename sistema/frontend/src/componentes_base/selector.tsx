import { useId, type SelectHTMLAttributes } from "react";
import estilos from "./campo_texto.module.css";

export interface OpcionSelector {
  valor: string;
  etiqueta: string;
}

interface Propiedades extends SelectHTMLAttributes<HTMLSelectElement> {
  etiqueta: string;
  opciones: OpcionSelector[];
  ayuda?: string;
  error?: string;
}

export function Selector({
  etiqueta,
  opciones,
  ayuda,
  error,
  id,
  className,
  ...resto
}: Propiedades) {
  const id_generado = useId();
  const id_campo = id ?? id_generado;

  return (
    <div className={estilos.contenedor}>
      <label className={estilos.etiqueta} htmlFor={id_campo}>
        {etiqueta}
      </label>
      <select
        id={id_campo}
        className={[estilos.entrada, error ? estilos.entrada_con_error : "", className]
          .filter(Boolean)
          .join(" ")}
        aria-invalid={error ? true : undefined}
        {...resto}
      >
        {opciones.map((opcion) => (
          <option key={opcion.valor} value={opcion.valor}>
            {opcion.etiqueta}
          </option>
        ))}
      </select>
      {error ? (
        <span className={estilos.error}>{error}</span>
      ) : ayuda ? (
        <span className={estilos.ayuda}>{ayuda}</span>
      ) : null}
    </div>
  );
}
