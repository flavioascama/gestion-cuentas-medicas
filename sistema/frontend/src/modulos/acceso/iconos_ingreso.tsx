// Íconos de la tarjeta de ingreso (Fase 39): campos, botón y línea de
// confianza. Mismo criterio de trazo que el resto de sets del sistema;
// acotado a esta pantalla.

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

export function IconoPersona(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6" />
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

export function IconoFlechaDerecha(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" {...props}>
      <path
        d="M3 8h10m0 0-4-4m4 4-4 4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconoEscudo(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase width={14} height={14} {...props}>
      <path d="M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </IconoBase>
  );
}
