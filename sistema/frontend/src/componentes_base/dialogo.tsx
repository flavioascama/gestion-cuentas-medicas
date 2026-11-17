import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import estilos from "./dialogo.module.css";

interface Propiedades {
  titulo: string;
  children: ReactNode;
  acciones: ReactNode;
  al_cerrar: () => void;
  ancho?: "normal" | "mediano" | "grande";
}

const _ENFOCABLES =
  "button:not([disabled]), input:not([disabled]), select:not([disabled]), " +
  'textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

function controles_enfocables(caja: HTMLElement): HTMLElement[] {
  return [...caja.querySelectorAll<HTMLElement>(_ENFOCABLES)];
}

// Tab y Mayus+Tab no salen del dialogo: del ultimo control se vuelve al
// primero, y al reves.
function retener_foco(evento: KeyboardEvent, caja: HTMLElement): void {
  const controles = controles_enfocables(caja);
  const primero = controles[0];
  const ultimo = controles[controles.length - 1];
  if (!primero || !ultimo) return;
  const activo = document.activeElement;
  if (evento.shiftKey && (activo === primero || activo === caja)) {
    evento.preventDefault();
    ultimo.focus();
  } else if (!evento.shiftKey && activo === ultimo) {
    evento.preventDefault();
    primero.focus();
  }
}

// Convenciones de un dialogo modal: el foco entra al abrir, Esc lo cierra,
// Tab no sale de el y, al cerrar, el foco vuelve al control que lo abrio.
function usar_foco_de_dialogo(caja: RefObject<HTMLDivElement>, al_cerrar: () => void): void {
  // El padre suele pasar una funcion nueva en cada render: se guarda en
  // una referencia para no reinstalar el efecto (y no mover el foco).
  const cerrar = useRef(al_cerrar);
  useEffect(() => {
    cerrar.current = al_cerrar;
  });

  useEffect(() => {
    const elemento = caja.current;
    if (!elemento) return;
    const anterior = document.activeElement;
    (controles_enfocables(elemento)[0] ?? elemento).focus();

    const al_tecla = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") cerrar.current();
      else if (evento.key === "Tab") retener_foco(evento, elemento);
    };
    document.addEventListener("keydown", al_tecla);
    return () => {
      document.removeEventListener("keydown", al_tecla);
      if (anterior instanceof HTMLElement) anterior.focus();
    };
  }, [caja]);
}

export function Dialogo({ titulo, children, acciones, al_cerrar, ancho = "normal" }: Propiedades) {
  const caja = useRef<HTMLDivElement>(null);
  usar_foco_de_dialogo(caja, al_cerrar);
  const clase_ancho = { normal: null, mediano: estilos.mediano, grande: estilos.grande }[ancho];
  const clase_caja = [estilos.caja, clase_ancho].filter(Boolean).join(" ");
  return (
    <div
      className={estilos.fondo}
      role="presentation"
      onClick={(evento) => {
        if (evento.target === evento.currentTarget) al_cerrar();
      }}
    >
      <div
        ref={caja}
        tabIndex={-1}
        className={clase_caja}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
      >
        <div className={estilos.titulo}>{titulo}</div>
        <div className={estilos.contenido}>{children}</div>
        <div className={estilos.acciones}>{acciones}</div>
      </div>
    </div>
  );
}
