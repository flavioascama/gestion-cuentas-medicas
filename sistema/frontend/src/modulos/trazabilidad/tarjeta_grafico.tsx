import { useState, type ReactNode } from "react";
import { ControlSegmentado, type OpcionSegmento } from "../../componentes_base/control_segmentado";
import estilos from "./tarjeta_grafico.module.css";

type Vista = "grafico" | "tabla";

const _VISTAS: OpcionSegmento<Vista>[] = [
  { valor: "grafico", etiqueta: "Gráfico" },
  { valor: "tabla", etiqueta: "Tabla" },
];

interface Propiedades {
  titulo: string;
  subtitulo?: string;
  controles?: ReactNode;
  tabla: ReactNode;
  children: ReactNode;
}

// Todo grafico del panel tiene su gemelo en tabla: ningun valor depende
// solo del color o de pasar el cursor por encima.
export function TarjetaGrafico({ titulo, subtitulo, controles, tabla, children }: Propiedades) {
  const [vista, set_vista] = useState<Vista>("grafico");

  return (
    <section className={estilos.tarjeta} aria-label={titulo}>
      <header className={estilos.cabecera}>
        <div className={estilos.textos}>
          <h2 className={estilos.titulo}>{titulo}</h2>
          {subtitulo ? <p className={estilos.subtitulo}>{subtitulo}</p> : null}
        </div>
        <div className={estilos.vista}>
          <ControlSegmentado
            opciones={_VISTAS}
            valor={vista}
            al_cambiar={set_vista}
            etiqueta_accesible={`Vista de ${titulo}`}
          />
        </div>
      </header>
      {controles ? <div className={estilos.controles}>{controles}</div> : null}
      <div className={estilos.cuerpo}>{vista === "grafico" ? children : tabla}</div>
    </section>
  );
}
