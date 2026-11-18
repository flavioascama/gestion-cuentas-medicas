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
import estilos from "./contingencia.module.css";

// CU-01, flujo alternativo (RF-23, AD-13, C-18): ACREDITA SALUD no
// respondio tras los reintentos; el analista registra el resultado que
// obtuvo por otro medio, con su sustento. El backend solo lo admite si la
// ultima verificacion de esta cuenta agoto sus reintentos.

const _INICIAL: SolicitudCoberturaContingencia = {
  condicion_cobertura: "ACREDITABLE",
  codigo_autorizacion: "",
  tipo_documento_autorizacion: "03",
  codigo_asegurado: "",
  tipo_afiliacion: "1",
  vigente_hasta: null,
  sustento: "",
};

type Campo = keyof SolicitudCoberturaContingencia;

// Los valores que admite cada dato (2026-11-18): antes se escribian los
// codigos a mano. Tipo de documento y de afiliacion son los del estandar
// TEDEF (Tabla 2, campos 12 y 7).
const _CONDICIONES: OpcionSelector[] = [
  { valor: "ACREDITABLE", etiqueta: "Acreditable" },
  { valor: "NO ACREDITABLE", etiqueta: "No acreditable" },
];
const _DOCUMENTOS_AUTORIZACION: OpcionSelector[] = [
  { valor: "01", etiqueta: "Solicitud de atención médica (SITEDS)" },
  { valor: "02", etiqueta: "Solicitud de chequeo médico (SITEDS)" },
  { valor: "03", etiqueta: "Carta de garantía" },
  { valor: "04", etiqueta: "Por código" },
  { valor: "06", etiqueta: "Otro tipo de autorización" },
  { valor: "07", etiqueta: "Declaración de accidente" },
  { valor: "99", etiqueta: "No aplica" },
];
const _AFILIACIONES: OpcionSelector[] = [
  { valor: "1", etiqueta: "Regular" },
  { valor: "2", etiqueta: "SCTR" },
  { valor: "3", etiqueta: "Potestativo (independiente)" },
  { valor: "4", etiqueta: "SCTR independiente" },
  { valor: "5", etiqueta: "Otros contributivos y complementario" },
  { valor: "6", etiqueta: "SOAT" },
  { valor: "7", etiqueta: "AFOCAT" },
  { valor: "8", etiqueta: "SIS subsidiado" },
  { valor: "9", etiqueta: "Semicontributivo" },
];

function CamposCobertura({
  datos,
  al_cambiar,
}: {
  datos: SolicitudCoberturaContingencia;
  al_cambiar: (campo: Campo, valor: string) => void;
}) {
  const campo = (clave: Campo, etiqueta: string) => (
    <CampoTexto
      etiqueta={etiqueta}
      value={datos[clave] ?? ""}
      onChange={(evento) => al_cambiar(clave, evento.target.value)}
    />
  );
  const lista = (clave: Campo, etiqueta: string, opciones: OpcionSelector[]) => (
    <Selector
      etiqueta={etiqueta}
      opciones={opciones}
      value={datos[clave] ?? ""}
      onChange={(evento) => al_cambiar(clave, evento.target.value)}
    />
  );
  return (
    <div className={estilos.formulario}>
      {lista("condicion_cobertura", "Condición de cobertura", _CONDICIONES)}
      {campo("codigo_autorizacion", "Código de acreditación")}
      {lista(
        "tipo_documento_autorizacion",
        "Tipo de documento de autorización",
        _DOCUMENTOS_AUTORIZACION,
      )}
      {campo("codigo_asegurado", "Código del asegurado en la IAFAS")}
      {lista("tipo_afiliacion", "Tipo de afiliación", _AFILIACIONES)}
      <CampoTexto
        etiqueta="Vigente hasta (opcional)"
        type="date"
        value={datos.vigente_hasta ?? ""}
        onChange={(evento) => al_cambiar("vigente_hasta", evento.target.value)}
      />
      <div className={estilos.ancho_completo}>{campo("sustento", "Sustento")}</div>
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
  const completo = !!datos.codigo_autorizacion.trim() && !!datos.codigo_asegurado.trim();

  const mutacion = useMutation({
    mutationFn: () => registrar_cobertura_contingencia(cuenta_id, datos),
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
            disabled={mutacion.isPending || !completo || !datos.sustento.trim()}
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
