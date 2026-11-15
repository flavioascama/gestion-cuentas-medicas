import type { ReactNode } from "react";
import type { Aviso } from "../../api/avisos";
import { formatear_hace } from "../../utilidades/formato";
import { describir_aviso } from "./catalogo_avisos";
import { ETIQUETA_SEVERIDAD, icono_severidad } from "./severidad_avisos";
import estilos from "./fila_aviso.module.css";

// Un aviso es una fila entera clicable (patron de bandeja de entrada):
// no hay que buscar un boton al extremo. Completa: severidad, titulo y
// hecho, cuenta o lote, y hace cuanto; compacta (panel de la campana):
// titulo, hecho y referencia en dos lineas.

interface Propiedades {
  aviso: Aviso;
  ahora: number;
  compacta?: boolean;
  al_abrir: (aviso: Aviso) => void;
}

function clase_tono(aviso: Aviso): string {
  return (aviso.atendido ? estilos.atendido : estilos[aviso.severidad]) ?? "";
}

function Contenedor({
  navegable,
  clase,
  al_abrir,
  children,
}: {
  navegable: boolean;
  clase: string;
  al_abrir: () => void;
  children: ReactNode;
}) {
  if (!navegable) return <div className={clase}>{children}</div>;
  return (
    <button type="button" className={`${clase} ${estilos.navegable}`} onClick={al_abrir}>
      {children}
    </button>
  );
}

export function FilaAviso({ aviso, ahora, compacta = false, al_abrir }: Propiedades) {
  const descripcion = describir_aviso(aviso);
  const Icono = icono_severidad(aviso.severidad, aviso.atendido);
  const etiqueta = aviso.atendido ? "Atendido" : (ETIQUETA_SEVERIDAD[aviso.severidad] ?? "");
  const hace = formatear_hace(aviso.ocurrido_en, ahora);
  const clase = `${estilos.fila} ${compacta ? estilos.compacta : ""} ${clase_tono(aviso)}`;

  return (
    <Contenedor
      navegable={descripcion.destino !== null}
      clase={clase}
      al_abrir={() => al_abrir(aviso)}
    >
      <span className={estilos.icono}>
        <Icono />
      </span>
      <span className={estilos.principal}>
        <span className={estilos.titulo}>{descripcion.titulo}</span>
        <span className={estilos.que_paso}>{descripcion.que_paso}</span>
        {compacta ? (
          <span className={estilos.meta}>
            {[descripcion.referencia, hace].filter(Boolean).join(" · ")}
          </span>
        ) : null}
      </span>
      {compacta ? null : (
        <>
          <span className={estilos.referencia}>{descripcion.referencia ?? "—"}</span>
          <span className={estilos.columna_etiqueta}>
            <span className={estilos.etiqueta}>{etiqueta}</span>
          </span>
          <span className={estilos.tiempo}>{hace}</span>
        </>
      )}
      <span className={estilos.chevron} aria-hidden="true">
        {descripcion.destino ? "›" : ""}
      </span>
    </Contenedor>
  );
}
