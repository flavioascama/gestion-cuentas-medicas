// Iconos de accion dentro de una fila de tabla (rediseno pedido por el
// usuario, 2026-11-11: antes una fila clicable no tenia ninguna senal
// visual de que lo fuera). Set propio, acotado a este uso -- mismo
// criterio de trazo que los demas sets del sistema (1.75, 24x24).

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

export function IconoOjo(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </IconoBase>
  );
}

export function IconoFlechaDerecha(props: SVGProps<SVGSVGElement>) {
  return (
    <IconoBase {...props}>
      <path d="m9 6 6 6-6 6" />
    </IconoBase>
  );
}
