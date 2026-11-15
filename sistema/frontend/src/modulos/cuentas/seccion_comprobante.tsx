import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { consultar_documentos_pago, type DocumentosPago } from "../../api/comprobante";
import { emitir_comprobante_pago } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import { DialogoNota, DialogoReemplazo } from "./dialogos_comprobante";
import { MOTIVOS_NOTA, TIPOS_NOTA } from "./etiquetas_comprobante";
import estilos from "./detalle_cuenta.module.css";

// CU-10 (reemplazo al refacturar) y RI-11 (una nota por comprobante).
const _ESTADOS_REEMPLAZO = new Set(["RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);
const _ESTADOS_NOTA = new Set(["FACTURADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);

function datos_documentos(documentos: DocumentosPago): { etiqueta: string; valor: string }[] {
  const { vigente, nota } = documentos;
  const datos = [
    { etiqueta: "Comprobante", valor: `${vigente.serie}-${vigente.numero}` },
    { etiqueta: "Emitido", valor: formatear_fecha(vigente.fecha_emision) },
  ];
  if (nota) {
    datos.push(
      {
        etiqueta: TIPOS_NOTA[nota.tipo] ?? "Nota",
        valor: `${nota.serie}-${nota.numero} · ${formatear_monto(nota.monto)} · ${formatear_fecha(nota.fecha)}`,
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

function AccionesDocumentos(props: { cuenta_id: number; estado: string; con_nota: boolean }) {
  const [dialogo, set_dialogo] = useState<"reemplazo" | "nota" | null>(null);
  const cerrar = () => set_dialogo(null);
  if (props.con_nota) return null;
  return (
    <div className={estilos.fila_accion}>
      {_ESTADOS_REEMPLAZO.has(props.estado) ? (
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

function EmitirComprobante({ cuenta_id }: { cuenta_id: number }) {
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: () => emitir_comprobante_pago(cuenta_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] }),
  });
  return (
    <>
      <div className={estilos.fila_accion}>
        <Boton variante="primario" onClick={() => mutacion.mutate()} disabled={mutacion.isPending}>
          Emitir comprobante de pago
        </Boton>
      </div>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo emitir." />
    </>
  );
}

export function SeccionComprobante({ cuenta_id, estado }: { cuenta_id: number; estado: string }) {
  const { sesion } = usar_sesion();
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comprobante"],
    queryFn: () => consultar_documentos_pago(cuenta_id),
  });
  const es_analista = Boolean(sesion?.roles.includes("analista"));
  const documentos = consulta.data ?? null;
  if (consulta.isPending || (!documentos && !es_analista)) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Comprobante de pago</div>
      {documentos ? (
        <div className={estilos.lista_compacta}>
          {datos_documentos(documentos).map((dato, indice) => (
            <div key={`${dato.etiqueta}-${indice}`} className={estilos.campo_dato}>
              <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
              <span className={estilos.valor_dato}>{dato.valor}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmitirComprobante cuenta_id={cuenta_id} />
      )}
      {documentos && es_analista ? (
        <AccionesDocumentos
          cuenta_id={cuenta_id}
          estado={estado}
          con_nota={Boolean(documentos.nota)}
        />
      ) : null}
    </div>
  );
}
