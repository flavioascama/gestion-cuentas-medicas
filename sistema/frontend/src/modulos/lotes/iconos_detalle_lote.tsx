// Iconos puntuales del detalle de lote (rediseno 2026-11-11): descarga
// del .S01 y estado vacio compacto de las tablas de observaciones/acuses.
// Mismo criterio de trazo que los demas sets del sistema (1.75, 24x24).

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

export function IconoDescarga(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M4 19h16" />
    </IconoBase>
  );
}

export function IconoCheck(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.5 2.5 2.5L16 9.5" />
    </IconoBase>
  );
}

// Pestana "Reporte mensual a SUSALUD" de la bandeja de lotes.
export function IconoCalendario(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18" />
      <path d="M8 3v4" />
      <path d="M16 3v4" />
    </IconoBase>
  );
}
