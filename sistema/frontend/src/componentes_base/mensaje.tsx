import estilos from "./mensaje.module.css";

interface Propiedades {
  tipo: "exito" | "advertencia" | "error";
  texto: string;
}

export function Mensaje({ tipo, texto }: Propiedades) {
  return (
    <div className={`${estilos.mensaje} ${estilos[tipo]}`} role="status">
      {texto}
    </div>
  );
}
