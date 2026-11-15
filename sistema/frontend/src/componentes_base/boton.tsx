import type { ButtonHTMLAttributes } from "react";
import estilos from "./boton.module.css";

type Variante = "primario" | "secundario" | "terciario" | "destructivo";

interface Propiedades extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
}

export function Boton({ variante = "secundario", className, ...resto }: Propiedades) {
  const clases = [estilos.boton, estilos[variante], className].filter(Boolean).join(" ");
  return <button type="button" className={clases} {...resto} />;
}
