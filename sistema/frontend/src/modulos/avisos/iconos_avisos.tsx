import type { SVGProps } from "react";

// Iconos de severidad de los avisos (SVG de trazo, mismo estilo que
// iconos_navegacion.tsx; sin emojis): el color lo pone quien los usa.

function Base(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    />
  );
}

// Critico: octagono con signo de exclamacion.
export function IconoCritico(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z" />
      <path d="M12 8v5" />
      <path d="M12 16.5v.5" />
    </Base>
  );
}

// Escalamiento: flecha hacia arriba sobre una barra (se elevo a la jefatura).
export function IconoEscalamiento(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M12 19V6" />
      <path d="m6 11 6-6 6 6" />
      <path d="M5 21h14" />
    </Base>
  );
}

// Por vencer: reloj.
export function IconoPorVencer(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </Base>
  );
}

// Atendido: marca de verificacion en un circulo.
export function IconoAtendido(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </Base>
  );
}
