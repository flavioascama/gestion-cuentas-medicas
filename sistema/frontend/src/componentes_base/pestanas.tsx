// Pestanas accesibles (patron WAI-ARIA APG "tabs", activacion
// automatica): icono + etiqueta por pestania, navegacion con flechas
// izquierda/derecha y Home/End, un unico panel visible a la vez (los
// demas quedan en el DOM con `hidden`, no se desmontan, para no perder
// el estado ni repetir consultas de React Query al volver a una
// pestania ya visitada). Usado primero en el detalle de cuenta
// (rediseno "resumen + pestanias"); candidato a reusarse en cualquier
// pantalla densa futura con el mismo problema.

import {
  useRef,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type ReactNode,
  type SVGProps,
} from "react";
import estilos from "./pestanas.module.css";

export interface DefinicionPestana {
  id: string;
  etiqueta: string;
  icono: ComponentType<SVGProps<SVGSVGElement>>;
  contenido: ReactNode;
}

function indice_desde_tecla(tecla: string, actual: number, total: number): number | null {
  if (tecla === "ArrowRight") return (actual + 1) % total;
  if (tecla === "ArrowLeft") return (actual - 1 + total) % total;
  if (tecla === "Home") return 0;
  if (tecla === "End") return total - 1;
  return null;
}

function BotonPestana({
  pestana,
  es_activa,
  referencia,
  al_seleccionar,
  al_presionar_tecla,
}: {
  pestana: DefinicionPestana;
  es_activa: boolean;
  referencia: (elemento: HTMLButtonElement | null) => void;
  al_seleccionar: () => void;
  al_presionar_tecla: (evento: KeyboardEvent<HTMLButtonElement>) => void;
}) {
  const Icono = pestana.icono;
  return (
    <button
      ref={referencia}
      type="button"
      role="tab"
      id={`pestana_${pestana.id}`}
      aria-selected={es_activa}
      aria-controls={`panel_${pestana.id}`}
      tabIndex={es_activa ? 0 : -1}
      className={`${estilos.pestana} ${es_activa ? estilos.pestana_activa : ""}`}
      onClick={al_seleccionar}
      onKeyDown={al_presionar_tecla}
    >
      <Icono />
      <span>{pestana.etiqueta}</span>
    </button>
  );
}

function PanelPestana({ pestana, visible }: { pestana: DefinicionPestana; visible: boolean }) {
  return (
    <div
      role="tabpanel"
      id={`panel_${pestana.id}`}
      aria-labelledby={`pestana_${pestana.id}`}
      hidden={!visible}
    >
      {pestana.contenido}
    </div>
  );
}

export function Pestanas({
  pestanas,
  etiqueta_lista,
}: {
  pestanas: DefinicionPestana[];
  etiqueta_lista: string;
}) {
  const [activa, set_activa] = useState(0);
  const referencias_boton = useRef<(HTMLButtonElement | null)[]>([]);
  const activa_segura = Math.min(activa, pestanas.length - 1);

  if (pestanas.length === 0) return null;

  function mover_foco(indice: number): void {
    set_activa(indice);
    referencias_boton.current[indice]?.focus();
  }

  return (
    <div className={estilos.contenedor}>
      <div role="tablist" aria-label={etiqueta_lista} className={estilos.lista}>
        {pestanas.map((pestana, indice) => (
          <BotonPestana
            key={pestana.id}
            pestana={pestana}
            es_activa={indice === activa_segura}
            referencia={(elemento) => {
              referencias_boton.current[indice] = elemento;
            }}
            al_seleccionar={() => set_activa(indice)}
            al_presionar_tecla={(evento) => {
              const siguiente = indice_desde_tecla(evento.key, indice, pestanas.length);
              if (siguiente === null) return;
              evento.preventDefault();
              mover_foco(siguiente);
            }}
          />
        ))}
      </div>
      {pestanas.map((pestana, indice) => (
        <PanelPestana key={pestana.id} pestana={pestana} visible={indice === activa_segura} />
      ))}
    </div>
  );
}
