import { CampoTexto } from "../../componentes_base/campo_texto";
import { Selector } from "../../componentes_base/selector";
import { CampoCie10 } from "./campo_cie10";
import type { usar_formulario_nueva_cuenta } from "./usar_formulario_nueva_cuenta";

const _OPCIONES_TIPO_DOCUMENTO = [
  { valor: "1", etiqueta: "DNI" },
  { valor: "2", etiqueta: "Carné de extranjería" },
  { valor: "3", etiqueta: "Pasaporte" },
];

type Formulario = ReturnType<typeof usar_formulario_nueva_cuenta>;

function CamposAsegurado({ formulario }: { formulario: Formulario }) {
  return (
    <>
      <Selector
        etiqueta="Tipo de documento del asegurado"
        opciones={_OPCIONES_TIPO_DOCUMENTO}
        value={formulario.tipo_documento_asegurado}
        onChange={(evento) => formulario.set_tipo_documento_asegurado(evento.target.value)}
      />
      <CampoTexto
        etiqueta="N.° de documento del asegurado"
        value={formulario.numero_documento_asegurado}
        onChange={(evento) => formulario.set_numero_documento_asegurado(evento.target.value)}
        maxLength={15}
      />
      <CampoTexto
        etiqueta="Nombres del asegurado"
        value={formulario.nombres_asegurado}
        onChange={(evento) => formulario.set_nombres_asegurado(evento.target.value)}
        maxLength={150}
      />
      <CampoTexto
        etiqueta="Apellidos del asegurado"
        value={formulario.apellidos_asegurado}
        onChange={(evento) => formulario.set_apellidos_asegurado(evento.target.value)}
        maxLength={150}
      />
    </>
  );
}

function CamposPrestacion({ formulario }: { formulario: Formulario }) {
  return (
    <>
      <Selector
        etiqueta="IAFAS"
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
      <CampoTexto
        etiqueta="Fecha de prestación"
        type="date"
        value={formulario.fecha_prestacion}
        onChange={(evento) => formulario.set_fecha_prestacion(evento.target.value)}
      />
      <CampoTexto
        etiqueta="Hora de prestación"
        type="time"
        value={formulario.hora_prestacion}
        onChange={(evento) => formulario.set_hora_prestacion(evento.target.value)}
      />
      <CampoCie10
        value={formulario.diagnostico_principal_cie10}
        onChange={formulario.set_diagnostico_principal_cie10}
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
