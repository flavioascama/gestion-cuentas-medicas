import estilos from "./linea_estados_lote.module.css";

export interface PasoLinea {
  etiqueta: string;
  estado: "completado" | "actual" | "pendiente" | "error";
  fecha_hora?: string;
}

interface Propiedades {
  pasos: PasoLinea[];
}

export function LineaEstadosLote({ pasos }: Propiedades) {
  return (
    <div className={estilos.linea}>
      {pasos.map((paso) => (
        <div key={paso.etiqueta} className={estilos.paso}>
          <span
            className={`${estilos.punto} ${paso.estado !== "pendiente" ? estilos[paso.estado] : ""}`}
            aria-hidden="true"
          />
          <span className={estilos.etiqueta}>{paso.etiqueta}</span>
          <span className={estilos.fecha_hora}>{paso.fecha_hora ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}
