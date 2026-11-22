import type { RespuestaGenerarLote } from "../../api/lotes";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { CuentasConPendientes } from "./cuentas_con_pendientes";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  resultado: RespuestaGenerarLote;
  al_cerrar: () => void;
  al_ver_lote: (lote_id: number) => void;
}

// Si el lote no se pudo generar, dice de que cuenta se trata y que le
// falta, con el enlace para completarlo. Sin el informe del estandar.
function LoteNoGenerado({ resultado }: { resultado: RespuestaGenerarLote }) {
  const cuentas = resultado.cuentas_con_pendientes ?? [];
  const motivos = [
    ...new Set(resultado.hallazgos.filter((h) => h.severidad === "error").map((h) => h.mensaje)),
  ];
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
      {cuentas.length === 0 ? (
        <ul className={estilos.lista_pendientes}>
          {motivos.map((motivo) => (
            <li key={motivo}>{motivo}</li>
          ))}
        </ul>
      ) : null}
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
