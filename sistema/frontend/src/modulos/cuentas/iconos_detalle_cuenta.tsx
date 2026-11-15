// Set de iconos de linea para las pestanias del detalle de cuenta
// (rediseno "resumen + pestanias", confirmado por el usuario). Mismo
// criterio de trazo que iconos_navegacion.tsx,
// pero acotado solo a esta pantalla -- no se usan en ninguna otra.

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

export function IconoProcedimientos(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M8 4h8a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z" />
      <path d="M9 3h6v3H9z" />
      <path d="m9 13 2 2 4-4" />
    </IconoBase>
  );
}

export function IconoFarmacia(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="4" y="9" width="16" height="7" rx="3.5" transform="rotate(-45 12 12.5)" />
      <path d="M9.5 9.5 14.5 14.5" />
    </IconoBase>
  );
}

export function IconoObservaciones(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M4 5h16v11H9l-4 4V5Z" />
      <path d="M12 8v4" />
      <path d="M12 14.5h.01" />
    </IconoBase>
  );
}

export function IconoLiquidacion(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
      <path d="M3 10h18" />
      <path d="M16 14h2" />
    </IconoBase>
  );
}

export function IconoCierre(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <rect x="5" y="11" width="14" height="9" rx="1.5" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
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

export function IconoHistorial(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l3 2" />
      <path d="M9 2h6" />
    </IconoBase>
  );
}
