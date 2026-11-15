import type { RespuestaSugerenciaCpms } from "../../api/cpms";
import { CampoTexto } from "../../componentes_base/campo_texto";
import estilos from "./asistente_cpms.module.css";

interface PropiedadesFormulario {
  descripcion: string;
  al_cambiar: (valor: string) => void;
  buscando: boolean;
}

export function FormularioBusquedaCpms({
  descripcion,
  al_cambiar,
  buscando,
}: PropiedadesFormulario) {
  return (
    <div className={estilos.busqueda}>
      <div className={estilos.campo_descripcion}>
        <CampoTexto
          etiqueta="Descripción del procedimiento"
          value={descripcion}
          onChange={(evento) => al_cambiar(evento.target.value)}
        />
      </div>
      {buscando ? <span className={estilos.buscando}>Buscando…</span> : null}
    </div>
  );
}

export function ResultadoBusquedaCpms({ resultado }: { resultado: RespuestaSugerenciaCpms }) {
  return (
    <div className={estilos.version}>
      Catálogo CPMS versión {resultado.cpms_version_etiqueta}
      {resultado.coincidencia_exacta ? " — coincidencia exacta por código" : ""}
    </div>
  );
}
