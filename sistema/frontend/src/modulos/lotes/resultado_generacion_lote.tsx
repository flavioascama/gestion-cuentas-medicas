import type { RespuestaGenerarLote } from "../../api/lotes";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { InformePrevalidacion } from "./informe_prevalidacion";

interface Propiedades {
  resultado: RespuestaGenerarLote;
  al_cerrar: () => void;
  al_ver_lote: (lote_id: number) => void;
}

export function ResultadoGeneracionLote({ resultado, al_cerrar, al_ver_lote }: Propiedades) {
  const lote_id = resultado.lote_id;
  return (
    <Dialogo
      titulo="Resultado de la generación"
      al_cerrar={al_cerrar}
      acciones={
        resultado.conforme && lote_id !== null ? (
          <Boton variante="primario" onClick={() => al_ver_lote(lote_id)}>
            Ver el lote
          </Boton>
        ) : (
          <Boton variante="secundario" onClick={al_cerrar}>
            Cerrar
          </Boton>
        )
      }
    >
      {resultado.conforme ? (
        <Mensaje tipo="exito" texto={`Lote ${resultado.numero_lote} generado y conforme.`} />
      ) : (
        <>
          <Mensaje tipo="error" texto={`El lote ${resultado.numero_lote} no es conforme.`} />
          <InformePrevalidacion hallazgos={resultado.hallazgos} />
        </>
      )}
    </Dialogo>
  );
}
