// Set de íconos de línea para la barra lateral y sus controles, usado en
// toda la aplicación (Fase 39, GUIA_DISENO_INTERFAZ.md Sección 4: la barra
// ya permitía "texto con ícono pequeño opcional"). Mismo criterio de trazo
// que los demas sets del sistema, cada uno acotado a su propia pantalla.

import type { SVGProps } from "react";

function IconoBase(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    />
  );
}

export function IconoMenu(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true" {...props}>
      <rect width="18" height="2" rx="1" fill="currentColor" />
      <rect y="6" width="18" height="2" rx="1" fill="currentColor" />
      <rect y="12" width="18" height="2" rx="1" fill="currentColor" />
    </svg>
  );
}

export function IconoChevron(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true" {...props}>
      <path
        d="M4 10l4-4 4 4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconoFlechaBarra(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true" {...props}>
      <path
        d="M10 2 4 8l6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconoCuentas(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v4h4" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </IconoBase>
  );
}

export function IconoLotes(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="m3 7 9-4 9 4-9 4-9-4Z" />
      <path d="M3 7v10l9 4 9-4V7" />
      <path d="M12 11v10" />
    </IconoBase>
  );
}

export function IconoComunicaciones(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </IconoBase>
  );
}

export function IconoAnulaciones(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 8.5 7 7m0-7-7 7" />
    </IconoBase>
  );
}

export function IconoIndicadores(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M4 20V10" />
      <path d="M12 20V4" />
      <path d="M20 20v-7" />
    </IconoBase>
  );
}

export function IconoAdministracion(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 13a8 8 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a8 8 0 0 0-1.7-1L14.8 3h-4l-.5 2.9a8 8 0 0 0-1.7 1l-2.5-1-2 3.5L6.2 11a8 8 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a8 8 0 0 0 1.7 1l.5 2.9h4l.5-2.9a8 8 0 0 0 1.7-1l2.5 1 2-3.5-2.1-1.6Z" />
    </IconoBase>
  );
}

export function IconoCandado(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="5" y="11" width="14" height="9" rx="1.5" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </IconoBase>
  );
}

export function IconoCerrarSesion(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </IconoBase>
  );
}

export function IconoSol(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8" />
    </IconoBase>
  );
}

// Portapapeles con marca de revision: los registros manuales en
// contingencia que el jefe revisa (C-18).
export function IconoContingencias(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M9 4h6v3H9z" />
      <path d="M15 5h2a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2" />
      <path d="m9 14 2 2 4-4" />
    </IconoBase>
  );
}

export function IconoFlechaIzquierda(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </IconoBase>
  );
}

export function IconoCampana(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </IconoBase>
  );
}

export function IconoLuna(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
    </IconoBase>
  );
}

// Pantallas de la administracion (rediseno 2026-11-15); "Parametros" usa
// IconoAdministracion (engranaje).
export function IconoUsuarios(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M16 14.2a5 5 0 0 1 5 5.8" />
    </IconoBase>
  );
}

export function IconoAseguradoras(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3Z" />
      <path d="M9 12l2 2 4-4" />
    </IconoBase>
  );
}

export function IconoRobot(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="4" y="8" width="16" height="11" rx="2" />
      <path d="M12 4v4" />
      <path d="M9 13h.01" />
      <path d="M15 13h.01" />
      <path d="M9 16h6" />
    </IconoBase>
  );
}

export function IconoCatalogos(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z" />
      <path d="M4 19a2 2 0 0 1 2-2h13" />
      <path d="M9 7h6" />
    </IconoBase>
  );
}
