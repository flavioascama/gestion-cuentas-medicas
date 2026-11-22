import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { consultar_documentos_pago, type DocumentosPago } from "../../api/comprobante";
import { Boton } from "../../componentes_base/boton";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { DialogoEmitirComprobante, DialogoNota, DialogoReemplazo } from "./dialogos_comprobante";
import { MOTIVOS_NOTA, TIPOS_NOTA } from "./etiquetas_comprobante";
import { usar_en_correccion_validador } from "./usar_cuentas";
import estilos from "./detalle_cuenta.module.css";

// CU-10 (reemplazo al refacturar, y si el validador observo el lote) y
// RI-11 (una nota por comprobante).
const _ESTADOS_REEMPLAZO = new Set(["RECHAZADA", "GLOSADA"]);
const _ESTADOS_NOTA = new Set(["FACTURADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);

function datos_documentos(documentos: DocumentosPago): { etiqueta: string; valor: string }[] {
  const { vigente, nota } = documentos;
  const datos = [
    { etiqueta: "Comprobante", valor: `${vigente.serie}-${vigente.numero}` },
    { etiqueta: "Emitido", valor: formatear_fecha(vigente.fecha_emision) },
  ];
  // Lo que factura el comprobante, con la misma regla que el lote.
  if (vigente.total != null) {
    datos.push(
      { etiqueta: "Valor de venta", valor: formatear_monto(vigente.valor_venta ?? 0) },
      { etiqueta: "IGV", valor: formatear_monto(vigente.igv ?? 0) },
      { etiqueta: "Total", valor: formatear_monto(vigente.total) },
    );
  }
  if (nota) {
    datos.push(
      {
        etiqueta: TIPOS_NOTA[nota.tipo] ?? "Nota",
        valor: `${nota.serie}-${nota.numero} · ${formatear_monto(nota.monto)} sin IGV · ${formatear_fecha(nota.fecha)}`,
      },
      { etiqueta: "Motivo de la nota", valor: MOTIVOS_NOTA[nota.motivo] ?? nota.motivo },
    );
  }
  for (const anterior of documentos.reemplazados) {
    datos.push({
      etiqueta: "Reemplaza a",
      valor: `${anterior.serie}-${anterior.numero} (${formatear_fecha(anterior.fecha_emision)})`,
    });
  }
  return datos;
}

// En Facturada, Rechazada y Glosada, el reemplazo solo si el servidor dice
// que el comprobante ya no refleja la cuenta.
function admite_reemplazo(estado: string, desfasado: boolean, en_correccion: boolean): boolean {
  const con_reemplazo = estado === "FACTURADA" || _ESTADOS_REEMPLAZO.has(estado);
  return en_correccion || (con_reemplazo && desfasado);
}

function AccionesDocumentos(props: {
  cuenta_id: number;
  estado: string;
  nota: DocumentosPago["nota"];
  desfasado: boolean;
}) {
  const [dialogo, set_dialogo] = useState<"reemplazo" | "nota" | null>(null);
  const en_correccion = usar_en_correccion_validador(props.cuenta_id);
  const cerrar = () => set_dialogo(null);
  // RI-11: una nota por comprobante, y la nota no se corrige.
  if (props.nota) {
    const tipo = (TIPOS_NOTA[props.nota.tipo] ?? "Nota").toLowerCase();
    return (
      <div className={estilos.fila_accion}>
        <span>
          El comprobante ya tiene su {tipo} {props.nota.serie}-{props.nota.numero}.
        </span>
      </div>
    );
  }
  return (
    <div className={estilos.fila_accion}>
      {admite_reemplazo(props.estado, props.desfasado, en_correccion) ? (
        <Boton variante="secundario" onClick={() => set_dialogo("reemplazo")}>
          Emitir comprobante de reemplazo
        </Boton>
      ) : null}
      {_ESTADOS_NOTA.has(props.estado) ? (
        <Boton variante="secundario" onClick={() => set_dialogo("nota")}>
          Registrar nota
        </Boton>
      ) : null}
      {dialogo === "reemplazo" ? (
        <DialogoReemplazo cuenta_id={props.cuenta_id} al_cerrar={cerrar} />
      ) : null}
      {dialogo === "nota" ? <DialogoNota cuenta_id={props.cuenta_id} al_cerrar={cerrar} /> : null}
    </div>
  );
}

const _LISTA = new Intl.ListFormat("es", { type: "conjunction" });

// El comprobante va al final: sin acreditacion, diagnostico y al menos un
// procedimiento no hay nada que facturar (2026-11-18).
function EmitirComprobante({ cuenta_id, faltantes }: { cuenta_id: number; faltantes: string[] }) {
  const [confirmar, set_confirmar] = useState(false);
  return (
    <div className={estilos.fila_accion}>
      <Boton
        variante="primario"
        onClick={() => set_confirmar(true)}
        disabled={faltantes.length > 0}
      >
        Emitir comprobante de pago
      </Boton>
      {faltantes.length > 0 ? <span>Antes falta: {_LISTA.format(faltantes)}.</span> : null}
      {confirmar ? (
        <DialogoEmitirComprobante cuenta_id={cuenta_id} al_cerrar={() => set_confirmar(false)} />
      ) : null}
    </div>
  );
}

// El servidor dice si el comprobante vigente ya no refleja la cuenta.
function AvisoDesfasado({ documentos }: { documentos: DocumentosPago | null }) {
  if (!documentos?.desfasado) return null;
  return (
    <div className={estilos.fila_accion}>
      <span>El comprobante ya no refleja la cuenta.</span>
    </div>
  );
}

// Paso "Comprobante de pago" de la linea de la cuenta.
export function ContenidoComprobante({
  cuenta_id,
  estado,
  faltantes,
}: {
  cuenta_id: number;
  estado: string;
  faltantes: string[];
}) {
  const { sesion } = usar_sesion();
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comprobante"],
    queryFn: () => consultar_documentos_pago(cuenta_id),
  });
  const es_analista = Boolean(sesion?.roles.includes("analista"));
  const documentos = consulta.data ?? null;
  if (consulta.isPending || (!documentos && !es_analista)) return null;

  return (
    <>
      {documentos ? (
        <div className={estilos.datos_en_linea}>
          {datos_documentos(documentos).map((dato, indice) => (
            <div key={`${dato.etiqueta}-${indice}`} className={estilos.campo_dato}>
              <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
              <span className={estilos.valor_dato}>{dato.valor}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmitirComprobante cuenta_id={cuenta_id} faltantes={faltantes} />
      )}
      <AvisoDesfasado documentos={documentos} />
      {documentos && es_analista ? (
        <AccionesDocumentos
          cuenta_id={cuenta_id}
          estado={estado}
          nota={documentos.nota}
          desfasado={documentos.desfasado}
        />
      ) : null}
    </>
  );
}
