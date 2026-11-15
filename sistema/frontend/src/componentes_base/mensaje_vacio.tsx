import estilos from "./mensaje_vacio.module.css";

interface Propiedades {
  texto: string;
}

export function MensajeVacio({ texto }: Propiedades) {
  return <div className={estilos.contenedor}>{texto}</div>;
}
