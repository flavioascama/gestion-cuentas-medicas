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

// La regla de la trama (Tabla 2, campo 10): el DNI lleva 8 dígitos; los
// demás documentos, no en blanco. El mismo texto lo da el servidor.
export function error_numero_documento(tipo: string, numero: string): string | undefined {
  if (numero === "") return undefined;
  if (tipo === "1" && !/^\d{8}$/.test(numero)) return "El DNI debe tener exactamente 8 dígitos.";
  if (numero.trim() === "") return "Ingrese el número de documento.";
  return undefined;
}

// Con el documento, trae del registro de la clinica los nombres y la IAFAS
// del asegurado (2026-11-18): solo se escriben si es la primera vez que se
// atiende. El numero no queda guardado en la memoria de consultas.
// Mientras se busca no se registra: los nombres que se guardan son los que se ven.
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
  const buscando = documento_buscable(tipo, escrito) && (!buscable || consulta.isFetching);
  return { registrado: buscable ? (consulta.data ?? null) : null, buscando };
}

function usar_campos_asegurado() {
  const [tipo_documento_asegurado, set_tipo_documento_asegurado] = useState("1");
  const [numero_documento_asegurado, set_numero_documento_asegurado] = useState("");
  const [nombres_escritos, set_nombres_asegurado] = useState("");
  const [apellidos_escritos, set_apellidos_asegurado] = useState("");
  const { registrado: asegurado_registrado, buscando: buscando_asegurado } =
    usar_asegurado_registrado(tipo_documento_asegurado, numero_documento_asegurado);

  return {
    tipo_documento_asegurado,
    numero_documento_asegurado,
    error_documento: error_numero_documento(tipo_documento_asegurado, numero_documento_asegurado),
    nombres_asegurado: asegurado_registrado?.nombres ?? nombres_escritos,
    apellidos_asegurado: asegurado_registrado?.apellidos ?? apellidos_escritos,
    asegurado_registrado,
    buscando_asegurado,
    set_tipo_documento_asegurado,
    set_numero_documento_asegurado,
    set_nombres_asegurado,
    set_apellidos_asegurado,
  };
}

// Mientras se busca el documento tampoco se registra.
function asegurado_incompleto(a: ReturnType<typeof usar_campos_asegurado>): boolean {
  return (
    !a.numero_documento_asegurado ||
    Boolean(a.error_documento) ||
    a.buscando_asegurado ||
    !a.nombres_asegurado.trim() ||
    !a.apellidos_asegurado.trim()
  );
}

// La prestacion no puede ser posterior a hoy (igual que el servidor).
function error_fecha_prestacion(fecha: string): string | undefined {
  return fecha > fecha_local_hoy()
    ? "La fecha de prestación no puede ser posterior a hoy."
    : undefined;
}

// El diagnostico es opcional: vacio o elegido de la lista, nunca un texto sin elegir.
function escrito_sin_elegir(escrito: string, elegido: string): boolean {
  return escrito.trim() !== "" && !elegido;
}

export function usar_formulario_nueva_cuenta() {
  const asegurado = usar_campos_asegurado();
  const [iafas_elegida, set_iafas_id] = useState("");
  // La cuenta se registra en la admision: se propone el momento actual.
  const [fecha_prestacion, set_fecha_prestacion] = useState(fecha_local_hoy);
  const [hora_prestacion, set_hora_prestacion] = useState(hora_local_ahora);
  const [diagnostico_principal_cie10, set_diagnostico_principal_cie10] = useState("");
  const [diagnostico_escrito, set_diagnostico_escrito] = useState("");

  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  // La IAFAS del asegurado ya registrado queda propuesta; se puede cambiar.
  const iafas_registrada = asegurado.asegurado_registrado?.iafas_id;
  const iafas_id = iafas_elegida || (iafas_registrada ? String(iafas_registrada) : "");

  const error_fecha = error_fecha_prestacion(fecha_prestacion);

  const falta_completar =
    asegurado_incompleto(asegurado) ||
    !iafas_id ||
    !fecha_prestacion ||
    Boolean(error_fecha) ||
    !hora_prestacion;

  function a_solicitud(): SolicitudNuevaCuenta {
    return {
      tipo_documento_asegurado: asegurado.tipo_documento_asegurado,
      numero_documento_asegurado: asegurado.numero_documento_asegurado,
      nombres_asegurado: asegurado.nombres_asegurado.trim(),
      apellidos_asegurado: asegurado.apellidos_asegurado.trim(),
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
    error_fecha,
    hora_prestacion,
    diagnostico_principal_cie10,
    consulta_iafas,
    falta_completar,
    diagnostico_sin_elegir: escrito_sin_elegir(diagnostico_escrito, diagnostico_principal_cie10),
    set_iafas_id,
    set_fecha_prestacion,
    set_hora_prestacion,
    set_diagnostico_principal_cie10,
    set_diagnostico_escrito,
    a_solicitud,
  };
}
