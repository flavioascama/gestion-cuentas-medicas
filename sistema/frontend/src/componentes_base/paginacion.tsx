import { TAMANIO_PAGINA } from "./paginar";
import estilos from "./paginacion.module.css";

interface Propiedades {
  pagina: number;
  total_paginas: number;
  total_registros: number;
  al_cambiar_pagina: (pagina: number) => void;
  etiqueta_entidad?: string;
}

export function Paginacion({
  pagina,
  total_paginas,
  total_registros,
  al_cambiar_pagina,
  etiqueta_entidad = "registros",
}: Propiedades) {
  // Una sola pagina: no hay nada que paginar, y mostrar el control de
  // todas formas solo serian dos botones deshabilitados sin proposito
  // (Seccion 1, "nada que distraiga del trabajo"). Cada bandeja llama a
  // este componente siempre, sin un condicional propio repetido.
  if (total_paginas <= 1) return null;

  const inicio = (pagina - 1) * TAMANIO_PAGINA + 1;
  const fin = Math.min(pagina * TAMANIO_PAGINA, total_registros);

  return (
    <div className={estilos.pie}>
      <span>
        Mostrando {inicio}–{fin} de {total_registros} {etiqueta_entidad}
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
          Página {pagina} de {Math.max(total_paginas, 1)}
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
