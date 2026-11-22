import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  disponibilidad_cobertura_contingencia,
  registrar_cobertura_contingencia,
  type SolicitudCoberturaContingencia,
} from "../../api/contingencia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector, type OpcionSelector } from "../../componentes_base/selector";
import { AFILIACIONES, DOCUMENTOS_AUTORIZACION, TIPOS_COPAGO } from "./catalogos_cobertura";
import estilos from "./contingencia.module.css";

// CU-01, flujo alternativo (RF-23, AD-13, C-18): ACREDITA SALUD no
// respondio tras los reintentos; el analista registra el resultado que
// obtuvo por otro medio, con su sustento. El backend solo lo admite si la
// ultima verificacion de esta cuenta agoto sus reintentos.

// Las mismas cotas que el servidor (esquemas_contingencia.py y
// LONGITUD_MINIMA_SUSTENTO).
const _LARGO_MINIMO_SUSTENTO = 10;

const _INICIAL: SolicitudCoberturaContingencia = {
  condicion_cobertura: "ACREDITABLE",
  codigo_autorizacion: "",
  tipo_documento_autorizacion: "01",
  codigo_asegurado: "",
  tipo_afiliacion: "1",
  vigente_hasta: null,
  sustento: "",
  plan: null,
  tipo_copago: "ninguno",
};

type Campo = keyof SolicitudCoberturaContingencia;

// El valor del copago se escribe en un solo campo: es el monto si el copago
// es fijo y el porcentaje si es coaseguro.
function cuerpo_solicitud(datos: SolicitudCoberturaContingencia): SolicitudCoberturaContingencia {
  const valor = datos.monto_copago_fijo ?? null;
  return {
    ...datos,
    monto_copago_fijo: datos.tipo_copago === "fijo" ? valor : null,
    porcentaje_coaseguro: datos.tipo_copago === "coaseguro" ? Number(valor) : null,
  };
}

function datos_completos(datos: SolicitudCoberturaContingencia): boolean {
  const copago_completo =
    datos.tipo_copago === "ninguno" || Number(datos.monto_copago_fijo ?? 0) > 0;
  return (
    !!datos.codigo_autorizacion.trim() &&
    !!datos.codigo_asegurado.trim() &&
    copago_completo &&
    datos.sustento.trim().length >= _LARGO_MINIMO_SUSTENTO
  );
}

function CampoValorCopago({
  datos,
  al_cambiar,
}: {
  datos: SolicitudCoberturaContingencia;
  al_cambiar: (campo: Campo, valor: string) => void;
}) {
  if (datos.tipo_copago === "ninguno") return null;
  const fijo = datos.tipo_copago === "fijo";
  return (
    <CampoTexto
      etiqueta={fijo ? "Monto del copago" : "Porcentaje de coaseguro"}
      obligatorio
      type="number"
      min={fijo ? 0.01 : 1}
      max={fijo ? undefined : 100}
      step={fijo ? 0.01 : 1}
      value={datos.monto_copago_fijo ?? ""}
      onChange={(evento) => al_cambiar("monto_copago_fijo", evento.target.value)}
    />
  );
}

function CamposCobertura({
  datos,
  al_cambiar,
}: {
  datos: SolicitudCoberturaContingencia;
  al_cambiar: (campo: Campo, valor: string) => void;
}) {
  const campo = (clave: Campo, etiqueta: string, largo_maximo: number) => (
    <CampoTexto
      etiqueta={etiqueta}
      obligatorio={clave !== "plan"}
      maxLength={largo_maximo}
      value={datos[clave] ?? ""}
      onChange={(evento) => al_cambiar(clave, evento.target.value)}
    />
  );
  const lista = (clave: Campo, etiqueta: string, opciones: OpcionSelector[]) => (
    <Selector
      etiqueta={etiqueta}
      obligatorio={clave !== "tipo_copago"}
      opciones={opciones}
      value={datos[clave] ?? ""}
      onChange={(evento) => al_cambiar(clave, evento.target.value)}
    />
  );
  return (
    <div className={estilos.formulario}>
      {campo("codigo_autorizacion", "Código de acreditación", 20)}
      {lista(
        "tipo_documento_autorizacion",
        "Tipo de documento de autorización",
        DOCUMENTOS_AUTORIZACION,
      )}
      {campo("codigo_asegurado", "Código del asegurado en la IAFAS", 20)}
      {lista("tipo_afiliacion", "Tipo de afiliación", AFILIACIONES)}
      {campo("plan", "Plan (opcional)", 100)}
      {lista("tipo_copago", "Tipo de copago", TIPOS_COPAGO)}
      <CampoValorCopago datos={datos} al_cambiar={al_cambiar} />
      <CampoTexto
        etiqueta="Vigente hasta (opcional)"
        type="date"
        value={datos.vigente_hasta ?? ""}
        onChange={(evento) => al_cambiar("vigente_hasta", evento.target.value)}
      />
      <div className={estilos.ancho_completo}>{campo("sustento", "Sustento", 1000)}</div>
    </div>
  );
}

function DialogoCoberturaContingencia({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [datos, set_datos] = useState(_INICIAL);
  const al_cambiar = (campo: Campo, valor: string) =>
    set_datos((previos) => ({
      ...previos,
      [campo]: campo === "vigente_hasta" && !valor ? null : valor,
    }));
  const completo = datos_completos(datos);

  const mutacion = useMutation({
    mutationFn: () => registrar_cobertura_contingencia(cuenta_id, cuerpo_solicitud(datos)),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_cerrar();
    },
  });

  return (
    <Dialogo
      titulo="Registrar la cobertura en modo de contingencia"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || !completo}
          >
            Registrar en contingencia
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo registrar." />
      <CamposCobertura datos={datos} al_cambiar={al_cambiar} />
    </Dialogo>
  );
}

export function AccionCoberturaContingencia({ cuenta_id }: { cuenta_id: number }) {
  const [abierto, set_abierto] = useState(false);
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "contingencia_cobertura"],
    queryFn: () => disponibilidad_cobertura_contingencia(cuenta_id),
  });
  if (!consulta.data?.habilitada) return null;

  return (
    <div className={estilos.aviso} role="status">
      <p className={estilos.texto_aviso}>ACREDITA SALUD no respondió tras los reintentos.</p>
      <Boton variante="secundario" onClick={() => set_abierto(true)}>
        Registrar en contingencia
      </Boton>
      {abierto ? (
        <DialogoCoberturaContingencia cuenta_id={cuenta_id} al_cerrar={() => set_abierto(false)} />
      ) : null}
    </div>
  );
}
