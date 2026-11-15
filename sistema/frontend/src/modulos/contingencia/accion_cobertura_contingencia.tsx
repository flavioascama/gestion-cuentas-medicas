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

function CamposCobertura({
  datos,
  al_cambiar,
}: {
  datos: SolicitudCoberturaContingencia;
  al_cambiar: (campo: Campo, valor: string) => void;
}) {
  const campo = (clave: Campo, etiqueta: string, ayuda?: string) => (
    <CampoTexto
      etiqueta={etiqueta}
      ayuda={ayuda}
      value={datos[clave] ?? ""}
      onChange={(evento) => al_cambiar(clave, evento.target.value)}
    />
  );
  return (
    <div className={estilos.formulario}>
      {campo("condicion_cobertura", "Condición de cobertura")}
      {campo("codigo_autorizacion", "Código de acreditación")}
      {campo("tipo_documento_autorizacion", "Tipo de documento de autorización")}
      {campo("codigo_asegurado", "Código del asegurado en la IAFAS")}
      {campo("tipo_afiliacion", "Tipo de afiliación")}
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
