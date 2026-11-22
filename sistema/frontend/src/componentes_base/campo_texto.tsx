import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import estilos from "./campo_texto.module.css";

interface Propiedades extends InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  ayuda?: string;
  error?: string;
  icono?: ReactNode;
  // Campo sin el cual no se puede guardar: un asterisco en la etiqueta.
  obligatorio?: boolean;
}

export function CampoTexto({
  etiqueta,
  ayuda,
  error,
  icono,
  obligatorio,
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
        {obligatorio ? " *" : null}
      </label>
      <div className={estilos.envoltorio_entrada}>
        {icono ? <span className={estilos.icono_entrada}>{icono}</span> : null}
        <input
          id={id_campo}
          className={[
            estilos.entrada,
            icono ? estilos.entrada_con_icono : "",
            error ? estilos.entrada_con_error : "",
            className,
          ]
            .filter(Boolean)
            .join(" ")}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id_campo}_error` : undefined}
          {...resto}
        />
      </div>
      {error ? (
        <span id={`${id_campo}_error`} className={estilos.error}>
          {error}
        </span>
      ) : ayuda ? (
        <span className={estilos.ayuda}>{ayuda}</span>
      ) : null}
    </div>
  );
}
