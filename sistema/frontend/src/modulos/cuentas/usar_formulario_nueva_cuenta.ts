import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { buscar_asegurado, type SolicitudNuevaCuenta } from "../../api/cuentas";
import { listar_iafas } from "../../api/iafas";
import { fecha_local_hoy, hora_local_ahora } from "../../utilidades/formato";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";

// Un documento se busca cuando ya puede estar completo: el DNI tiene 8 digitos.
function documento_buscable(tipo: string, numero: string): boolean {
  return tipo === "1" ? /^\d{8}$/.test(numero) : numero.length >= 6;
}

// Con el documento, trae del registro de la clinica los nombres y la IAFAS
// del asegurado (2026-11-18): solo se escriben si es la primera vez que se
// atiende. El numero no queda guardado en la memoria de consultas.
function usar_asegurado_registrado(tipo: string, numero: string) {
  const escrito = numero.trim();
  const diferido = usar_valor_diferido(escrito);
  const buscable = diferido === escrito && documento_buscable(tipo, escrito);
  const consulta = useQuery({
    queryKey: ["asegurado_registrado", tipo, diferido],
    queryFn: () => buscar_asegurado(tipo, diferido),
    enabled: buscable,
    gcTime: 0,
  });
  return buscable ? (consulta.data ?? null) : null;
}

function usar_campos_asegurado() {
  const [tipo_documento_asegurado, set_tipo_documento_asegurado] = useState("1");
  const [numero_documento_asegurado, set_numero_documento_asegurado] = useState("");
  const [nombres_escritos, set_nombres_asegurado] = useState("");
  const [apellidos_escritos, set_apellidos_asegurado] = useState("");
  const asegurado_registrado = usar_asegurado_registrado(
    tipo_documento_asegurado,
    numero_documento_asegurado,
  );

  return {
    tipo_documento_asegurado,
    numero_documento_asegurado,
    nombres_asegurado: asegurado_registrado?.nombres ?? nombres_escritos,
    apellidos_asegurado: asegurado_registrado?.apellidos ?? apellidos_escritos,
    asegurado_registrado,
    set_tipo_documento_asegurado,
    set_numero_documento_asegurado,
    set_nombres_asegurado,
    set_apellidos_asegurado,
  };
}

export function usar_formulario_nueva_cuenta() {
  const asegurado = usar_campos_asegurado();
  const [iafas_elegida, set_iafas_id] = useState("");
  // La cuenta se registra en la admision: se propone el momento actual.
  const [fecha_prestacion, set_fecha_prestacion] = useState(fecha_local_hoy);
  const [hora_prestacion, set_hora_prestacion] = useState(hora_local_ahora);
  const [diagnostico_principal_cie10, set_diagnostico_principal_cie10] = useState("");

  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  // La IAFAS del asegurado ya registrado queda propuesta; se puede cambiar.
  const iafas_registrada = asegurado.asegurado_registrado?.iafas_id;
  const iafas_id = iafas_elegida || (iafas_registrada ? String(iafas_registrada) : "");

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
