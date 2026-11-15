import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { SolicitudNuevaCuenta } from "../../api/cuentas";
import { listar_iafas } from "../../api/iafas";

function usar_campos_asegurado() {
  const [tipo_documento_asegurado, set_tipo_documento_asegurado] = useState("1");
  const [numero_documento_asegurado, set_numero_documento_asegurado] = useState("");
  const [nombres_asegurado, set_nombres_asegurado] = useState("");
  const [apellidos_asegurado, set_apellidos_asegurado] = useState("");

  return {
    tipo_documento_asegurado,
    numero_documento_asegurado,
    nombres_asegurado,
    apellidos_asegurado,
    set_tipo_documento_asegurado,
    set_numero_documento_asegurado,
    set_nombres_asegurado,
    set_apellidos_asegurado,
  };
}

export function usar_formulario_nueva_cuenta() {
  const asegurado = usar_campos_asegurado();
  const [iafas_id, set_iafas_id] = useState("");
  const [fecha_prestacion, set_fecha_prestacion] = useState("");
  const [hora_prestacion, set_hora_prestacion] = useState("");
  const [diagnostico_principal_cie10, set_diagnostico_principal_cie10] = useState("");

  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });

  const falta_completar =
    !asegurado.numero_documento_asegurado ||
    !asegurado.nombres_asegurado ||
    !asegurado.apellidos_asegurado ||
    !iafas_id ||
    !fecha_prestacion ||
    !hora_prestacion;

  function a_solicitud(): SolicitudNuevaCuenta {
    return {
      tipo_documento_asegurado: asegurado.tipo_documento_asegurado,
      numero_documento_asegurado: asegurado.numero_documento_asegurado,
      nombres_asegurado: asegurado.nombres_asegurado,
      apellidos_asegurado: asegurado.apellidos_asegurado,
      iafas_id: Number(iafas_id),
      fecha_prestacion,
      hora_prestacion: `${hora_prestacion}:00`,
      diagnostico_principal_cie10: diagnostico_principal_cie10 || null,
    };
  }

  return {
    ...asegurado,
    iafas_id,
    fecha_prestacion,
    hora_prestacion,
    diagnostico_principal_cie10,
    consulta_iafas,
    falta_completar,
    set_iafas_id,
    set_fecha_prestacion,
    set_hora_prestacion,
    set_diagnostico_principal_cie10,
    a_solicitud,
  };
}
