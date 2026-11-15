import { Link, useNavigate } from "react-router-dom";
import { ir_a_paso, type Recorrido } from "../navegacion/recorrido";
import { IconoFlechaIzquierda } from "./iconos_navegacion";
import estilos from "./barra_recorrido.module.css";

// Banda de contexto encima del titulo de un detalle abierto desde una
// lista (avisos, cuentas de un lote): dice de donde se vino y por que se
// esta aqui, y permite volver o pasar al anterior o al siguiente sin
// regresar a la lista.
export function BarraRecorrido({ recorrido }: { recorrido: Recorrido | null }) {
  const navegar = useNavigate();
  if (!recorrido) return null;
  const { indice, pasos } = recorrido;
  const paso = pasos[indice];

  return (
    <section
      className={estilos.barra}
      aria-label={`${recorrido.nombre} ${indice + 1} de ${pasos.length}`}
    >
      <Link to={recorrido.volver.ruta} className={estilos.volver}>
        <IconoFlechaIzquierda />
        <span>{recorrido.volver.etiqueta}</span>
      </Link>
      <div className={estilos.centro}>
        <span className={estilos.posicion}>
          {recorrido.nombre} {indice + 1} de {pasos.length}
        </span>
        {paso?.detalle ? <span className={estilos.detalle}>{paso.detalle}</span> : null}
      </div>
      <div className={estilos.pasos}>
        <button
          type="button"
          className={estilos.paso}
          onClick={() => ir_a_paso(navegar, recorrido, indice - 1)}
          disabled={indice === 0}
        >
          ‹ Anterior
        </button>
        <button
          type="button"
          className={estilos.paso}
          onClick={() => ir_a_paso(navegar, recorrido, indice + 1)}
          disabled={indice === pasos.length - 1}
        >
          Siguiente ›
        </button>
      </div>
    </section>
  );
}
