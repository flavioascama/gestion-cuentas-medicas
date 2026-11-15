import type { CandidatoCpms, RespuestaSugerenciaCpms } from "../../api/cpms";
import { DialogoConfirmarProcedimiento } from "./dialogo_confirmar_procedimiento";
import { ResultadoBusquedaCpms } from "./formulario_busqueda_cpms";
import { TablaCandidatos } from "./tabla_candidatos";

interface Propiedades {
  cuenta_id: number;
  descripcion: string;
  resultado: RespuestaSugerenciaCpms;
  candidato_elegido: CandidatoCpms | null;
  al_elegir: (candidato: CandidatoCpms | null) => void;
  al_confirmar: () => void;
}

export function ResultadosCpms({
  cuenta_id,
  descripcion,
  resultado,
  candidato_elegido,
  al_elegir,
  al_confirmar,
}: Propiedades) {
  return (
    <>
      <ResultadoBusquedaCpms resultado={resultado} />
      <TablaCandidatos
        candidatos={resultado.candidatos}
        puede_confirmar={Boolean(cuenta_id)}
        al_elegir={al_elegir}
      />
      {candidato_elegido ? (
        <DialogoConfirmarProcedimiento
          candidato={candidato_elegido}
          cuenta_id={cuenta_id}
          inicio_sugerencia={resultado.inicio_sugerencia}
          descripcion={descripcion}
          al_cerrar={() => al_elegir(null)}
          al_confirmar={al_confirmar}
        />
      ) : null}
    </>
  );
}
