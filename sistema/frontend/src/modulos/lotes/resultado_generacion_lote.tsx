import type { RespuestaGenerarLote } from "../../api/lotes";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { CuentasConPendientes } from "./cuentas_con_pendientes";
import { InformePrevalidacion } from "./informe_prevalidacion";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  resultado: RespuestaGenerarLote;
  al_cerrar: () => void;
  al_ver_lote: (lote_id: number) => void;
}

// Si el lote no se pudo generar, primero dice de que cuenta se trata y que
// le falta, con el enlace para completarlo (2026-11-18). El informe del
// estandar (tabla, campo y criterio) queda debajo, plegado.
function LoteNoGenerado({ resultado }: { resultado: RespuestaGenerarLote }) {
  const cuentas = resultado.cuentas_con_pendientes ?? [];
  return (
    <>
      <Mensaje
        tipo="error"
        texto={
          cuentas.length > 0
            ? "El lote no se generó: hay cuentas con datos pendientes."
            : "El lote no se generó."
        }
      />
      <CuentasConPendientes titulo="Cuentas por completar" cuentas={cuentas} />
      <details className={estilos.detalle_tecnico} open={cuentas.length === 0}>
        <summary>Detalle técnico</summary>
        <InformePrevalidacion hallazgos={resultado.hallazgos} />
      </details>
    </>
  );
}

export function ResultadoGeneracionLote({ resultado, al_cerrar, al_ver_lote }: Propiedades) {
  const lote_id = resultado.lote_id;
  return (
    <Dialogo
      titulo="Resultado de la generación"
      al_cerrar={al_cerrar}
      ancho="mediano"
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
        <LoteNoGenerado resultado={resultado} />
      )}
    </Dialogo>
  );
}
