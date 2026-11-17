import type { ReactNode } from "react";
import { TAMANIO_PAGINA } from "./paginar";
import estilos from "./paginacion.module.css";

interface Propiedades {
  pagina: number;
  total_paginas: number;
  total_registros: number;
  al_cambiar_pagina: (pagina: number) => void;
  etiqueta_entidad?: string;
}

function BarraPaginacion({
  posicion,
  pagina,
  total_paginas,
  total_registros,
  al_cambiar_pagina,
  etiqueta_entidad = "registros",
}: Propiedades & { posicion: "superior" | "inferior" }) {
  // Una sola pagina: no hay nada que paginar, y mostrar el control de
  // todas formas solo serian dos botones deshabilitados sin proposito
  // (Seccion 1, "nada que distraiga del trabajo"). Cada bandeja usa este
  // componente siempre, sin un condicional propio repetido.
  if (total_paginas <= 1) return null;

  const inicio = (pagina - 1) * TAMANIO_PAGINA + 1;
  const fin = Math.min(pagina * TAMANIO_PAGINA, total_registros);

  return (
    <div className={`${estilos.barra} ${estilos[posicion]}`}>
      <span>
        Mostrando{" "}
        <strong>
          {inicio}–{fin}
        </strong>{" "}
        de <strong>{total_registros}</strong> {etiqueta_entidad}
      </span>
      <div className={estilos.controles}>
        <button
          type="button"
          className={estilos.boton_pagina}
          disabled={pagina <= 1}
          onClick={() => al_cambiar_pagina(pagina - 1)}
        >
          Anterior
        </button>
        <span>
          Página <strong>{pagina}</strong> de {total_paginas}
        </span>
        <button
          type="button"
          className={estilos.boton_pagina}
          disabled={pagina >= total_paginas}
          onClick={() => al_cambiar_pagina(pagina + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}

// La paginacion va arriba y abajo de la tabla: quien no baja hasta el final
// de la pagina igual ve que la informacion continua en otras paginas.
export function ConPaginacion({ children, ...paginacion }: Propiedades & { children: ReactNode }) {
  return (
    <>
      <BarraPaginacion {...paginacion} posicion="superior" />
      {children}
      <BarraPaginacion {...paginacion} posicion="inferior" />
    </>
  );
}
