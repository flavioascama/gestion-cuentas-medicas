import { CampoTexto } from "../../componentes_base/campo_texto";
import { Selector } from "../../componentes_base/selector";
import { fecha_local_hoy } from "../../utilidades/formato";
import { CampoCie10 } from "./campo_cie10";
import { OPCIONES_TIPO_DOCUMENTO } from "./etiquetas_atencion";
import type { usar_formulario_nueva_cuenta } from "./usar_formulario_nueva_cuenta";

type Formulario = ReturnType<typeof usar_formulario_nueva_cuenta>;

function CamposAsegurado({ formulario }: { formulario: Formulario }) {
  // Un asegurado que la clinica ya atendio trae sus nombres del registro.
  const registrado = Boolean(formulario.asegurado_registrado);
  return (
    <>
      <Selector
        etiqueta="Tipo de documento del asegurado"
        obligatorio
        opciones={OPCIONES_TIPO_DOCUMENTO}
        value={formulario.tipo_documento_asegurado}
        onChange={(evento) => formulario.set_tipo_documento_asegurado(evento.target.value)}
      />
      <CampoTexto
        etiqueta="N.° de documento del asegurado"
        obligatorio
        value={formulario.numero_documento_asegurado}
        onChange={(evento) => formulario.set_numero_documento_asegurado(evento.target.value)}
        maxLength={15}
        error={formulario.error_documento}
      />
      <CampoTexto
        etiqueta="Nombres del asegurado"
        obligatorio
        value={formulario.nombres_asegurado}
        onChange={(evento) => formulario.set_nombres_asegurado(evento.target.value)}
        maxLength={150}
        disabled={registrado}
      />
      <CampoTexto
        etiqueta="Apellidos del asegurado"
        obligatorio
        value={formulario.apellidos_asegurado}
        onChange={(evento) => formulario.set_apellidos_asegurado(evento.target.value)}
        maxLength={150}
        disabled={registrado}
      />
    </>
  );
}

function CamposPrestacion({ formulario }: { formulario: Formulario }) {
  return (
    <>
      <Selector
        etiqueta="IAFAS"
        obligatorio
        opciones={[
          { valor: "", etiqueta: "Seleccione una IAFAS" },
          ...(formulario.consulta_iafas.data ?? []).map((i) => ({
            valor: String(i.id),
            etiqueta: i.razon_social,
          })),
        ]}
        value={formulario.iafas_id}
        onChange={(evento) => formulario.set_iafas_id(evento.target.value)}
      />
      <CampoCie10
        value={formulario.diagnostico_principal_cie10}
        onChange={formulario.set_diagnostico_principal_cie10}
        al_escribir={formulario.set_diagnostico_escrito}
      />
      <CampoTexto
        etiqueta="Fecha de prestación"
        obligatorio
        type="date"
        max={fecha_local_hoy()}
        value={formulario.fecha_prestacion}
        onChange={(evento) => formulario.set_fecha_prestacion(evento.target.value)}
        error={formulario.error_fecha}
      />
      <CampoTexto
        etiqueta="Hora de prestación"
        obligatorio
        type="time"
        value={formulario.hora_prestacion}
        onChange={(evento) => formulario.set_hora_prestacion(evento.target.value)}
      />
    </>
  );
}

export function CamposNuevaCuenta({ formulario }: { formulario: Formulario }) {
  return (
    <>
      <CamposAsegurado formulario={formulario} />
      <CamposPrestacion formulario={formulario} />
    </>
  );
}
