import type { Aviso } from "../../api/avisos";
import type { NombreRol } from "../../api/auth";
import { ruta_permitida } from "../../configuracion_rutas";
import { TIPOS_COMUNICACION, detalle_no_aplicada } from "../comunicaciones/columnas_comunicaciones";
import { MOTIVOS_REVISION } from "../comunicaciones/etiquetas_correos";
import { formatear_fecha, formatear_fecha_hora, formatear_periodo } from "../../utilidades/formato";

// Que significa cada aviso, en el lenguaje de la clinica: un titulo y el
// hecho (que paso), con la cuenta o el lote al que lleva. Sin consejos de
// que hacer (pedido del usuario, 2026-11-12: es un sistema clinico, no
// una guia).

export interface DescripcionAviso {
  titulo: string;
  que_paso: string;
  destino: string | null;
  referencia: string | null;
}

type Describir = (aviso: Aviso) => { titulo: string; que_paso: string };

function plazo(aviso: Aviso): string {
  const dias = aviso.datos.plazo_dias;
  return typeof dias === "number" && dias > 0 ? ` de ${dias} días` : "";
}

function plazo_48_horas(aviso: Aviso): string {
  return formatear_fecha_hora(
    new Date(Date.parse(aviso.ocurrido_en) + 48 * 3600 * 1000).toISOString(),
  );
}

function texto(aviso: Aviso, clave: string): string | null {
  const valor = aviso.datos[clave];
  return typeof valor === "string" && valor ? valor : null;
}

const _PLATAFORMAS: Record<string, string> = {
  acredita_salud: "ACREDITA SALUD",
  tedef_web: "TEDEF Web",
};

// Sin lote, el periodo no tuvo lotes y lo pendiente es la declaracion jurada.
function pendiente_susalud(aviso: Aviso): string {
  return aviso.lote_id
    ? "Lotes del periodo sin enviar a SUSALUD"
    : "Periodo sin lotes: falta registrar la declaración jurada ante SUSALUD";
}

const _VIAS_COMUNICACION: Record<string, string> = {
  PORTAL: " por el portal de la IAFAS",
  CORREO: " por correo electrónico",
};

const _TRABAJOS: Record<string, { titulo: string; que_paso: string }> = {
  CONSULTAR_COBERTURA: {
    titulo: "Cobertura sin verificar",
    que_paso: "ACREDITA SALUD no respondió a la consulta de acreditación.",
  },
  CARGAR_LOTE_VALIDADOR: {
    titulo: "Lote sin validar",
    que_paso: "El validador TEDEF Web no respondió a la carga del lote.",
  },
  MONITOREAR_RESPUESTA_IAFAS: {
    titulo: "Lote sin respuesta de la IAFAS",
    que_paso: "No llegó la respuesta de la IAFAS dentro del tiempo de espera.",
  },
  ENVIAR_LOTE_SUSALUD: {
    titulo: "Envío a SUSALUD sin completar",
    que_paso: "No se completó el envío de los lotes del periodo a SUSALUD.",
  },
  MONITOREAR_COMUNICACIONES_IAFAS: {
    titulo: "Comunicaciones de la IAFAS sin revisar",
    que_paso: "No se pudo revisar el portal y el correo de la IAFAS.",
  },
  ENVIAR_RESPUESTA_IAFAS: {
    titulo: "Respuesta a la IAFAS sin entregar",
    que_paso: "No se pudo entregar la respuesta en el portal de la IAFAS.",
  },
};

// Claves en minusculas: la convencion de nombres del proyecto exige
// snake_case en las propiedades; se busca con `tipo_evento.toLowerCase()`.
const _CATALOGO: Record<string, Describir> = {
  observacion_plazo_proximo_a_vencer: (a) => ({
    titulo: "Observación de la IAFAS por vencer",
    que_paso: `Está por vencer el plazo${plazo(a)} para responder la observación de la IAFAS.`,
  }),
  observacion_plazo_vencido_escalado: (a) => ({
    titulo: "Observación de la IAFAS vencida",
    que_paso: `Venció el plazo${plazo(a)} para responder la observación; escalado a la jefatura.`,
  }),
  observacion_reasignada: () => ({
    titulo: "Observación de la IAFAS reasignada",
    que_paso: "La jefatura reasignó el responsable de la observación.",
  }),
  lote_rechazado_plazo_proximo_a_vencer: (a) => ({
    titulo: "Cuenta rechazada: reenvío por vencer",
    que_paso: `Está por vencer el plazo${plazo(a)} para corregir y reenviar la cuenta rechazada.`,
  }),
  lote_rechazado_reenvio_pendiente_escalado: (a) => ({
    titulo: "Cuenta rechazada sin reenviar",
    que_paso: `Venció el plazo${plazo(a)} para corregir y reenviar la cuenta; escalado a la jefatura.`,
  }),
  auditoria_plazo_proximo_a_vencer: (a) => ({
    titulo: "Auditoría de la IAFAS por vencer",
    que_paso: `Está por vencer el plazo${plazo(a)} de la IAFAS para comunicar su auditoría.`,
  }),
  auditoria_excedida: (a) => ({
    titulo: "Auditoría de la IAFAS sin comunicar",
    que_paso: `La IAFAS no comunicó su auditoría en el plazo${plazo(a)}; escalado a la jefatura.`,
  }),
  liquidacion_pago_proximo_a_vencer: (a) => ({
    titulo: "Pago de la IAFAS por vencer",
    que_paso: `Está por vencer el plazo${plazo(a)} de la IAFAS para pagar la liquidación.`,
  }),
  liquidacion_pago_vencido_escalado: (a) => ({
    titulo: "Pago de la IAFAS vencido",
    que_paso: `La IAFAS no pagó la liquidación en el plazo${plazo(a)}; escalado a la jefatura.`,
  }),
  carta_garantia_proxima_a_vencer: (a) => {
    const hasta = texto(a, "vigente_hasta");
    return {
      titulo: "Cobertura por vencer",
      que_paso: `La cobertura vence${hasta ? ` el ${formatear_fecha(hasta)}` : " pronto"} y la cuenta no se remitió.`,
    };
  },
  susalud_envio_proximo_a_vencer: (a) => {
    const limite = texto(a, "fecha_limite");
    return {
      titulo: "Envío a SUSALUD por vencer",
      que_paso: `${pendiente_susalud(a)}; vence${limite ? ` el ${formatear_fecha(limite)}` : " pronto"}.`,
    };
  },
  susalud_envio_vencido_escalado: (a) => {
    const limite = texto(a, "fecha_limite");
    return {
      titulo: "Envío a SUSALUD vencido",
      que_paso: `${pendiente_susalud(a)}${limite ? `; venció el ${formatear_fecha(limite)}` : ""}; escalado a la jefatura.`,
    };
  },
  lote_rechazado: (a) => {
    const motivo = texto(a, "motivo");
    return {
      titulo: "Lote rechazado por la IAFAS",
      que_paso: motivo ? `Motivo: ${motivo}` : "La IAFAS rechazó el lote.",
    };
  },
  comunicacion_iafas_no_aplicada: (a) => {
    const tipo = TIPOS_COMUNICACION[texto(a, "tipo") ?? ""] ?? "Comunicación";
    const codigo = texto(a, "codigo");
    const via = _VIAS_COMUNICACION[texto(a, "canal") ?? ""] ?? "";
    const detalle = texto(a, "detalle");
    return {
      titulo: "Comunicación de la IAFAS no aplicada",
      que_paso: `${tipo}${codigo ? ` ${codigo}` : ""}${via}${
        detalle ? `: ${detalle_no_aplicada(detalle)}` : "."
      }`,
    };
  },
  correo_iafas_por_revisar: (a) => ({
    titulo: "Correo de la IAFAS por revisar",
    que_paso: `${texto(a, "remitente") ?? ""}: ${MOTIVOS_REVISION[texto(a, "motivo") ?? ""] ?? ""}`,
  }),
  // C-15: el incidente se comunica a la autoridad dentro de las 48 horas de
  // conocido (D.S. 016-2024-JUS, art. 34).
  ruptura_cadena_detectada: (a) => ({
    titulo: "Alteración en el registro de eventos",
    que_paso: `Se detectó un evento modificado fuera de la aplicación. Plazo de comunicación a la autoridad: ${plazo_48_horas(a)}.`,
  }),
  acceso_denegado: (a) => ({
    titulo: "Acceso no permitido",
    que_paso: `${a.actor ?? "Un usuario"} intentó una operación para la que no tiene permiso. Plazo de comunicación a la autoridad: ${plazo_48_horas(a)}.`,
  }),
  anulacion: (a) => {
    const motivo = texto(a, "motivo");
    return {
      titulo: "Anulación aprobada",
      que_paso: `${a.actor ?? "La jefatura"} aprobó la anulación; la cuenta quedó anulada.${motivo ? ` Motivo: ${motivo}` : ""}`,
    };
  },
  anulacion_rechazada: (a) => ({
    titulo: "Anulación rechazada",
    que_paso: `${a.actor ?? "La jefatura"} rechazó la anulación. Motivo: ${texto(a, "motivo") ?? "—"}`,
  }),
  contingencia_cobertura_registrada: (a) => ({
    titulo: "Acreditación registrada en contingencia",
    que_paso: texto(a, "sustento") ? `Sustento: ${texto(a, "sustento")}` : "Registro manual.",
  }),
  contingencia_validacion_registrada: (a) => ({
    titulo: "Validación registrada en contingencia",
    que_paso: texto(a, "sustento") ? `Sustento: ${texto(a, "sustento")}` : "Registro manual.",
  }),
  trabajo_agotado: (a) => {
    if (texto(a, "tipo_trabajo") === "INICIAR_SESION_PLATAFORMA") {
      const plataforma = _PLATAFORMAS[texto(a, "plataforma") ?? ""] ?? "la plataforma";
      return {
        titulo: `Ingreso a ${plataforma} sin completar`,
        que_paso: `No se pudo ingresar a ${plataforma}.`,
      };
    }
    return (
      _TRABAJOS[texto(a, "tipo_trabajo") ?? ""] ?? {
        titulo: "Operación sin completar",
        que_paso: "Una operación no se completó después de varios intentos.",
      }
    );
  },
};

// Donde se retoma lo que no se completo; undefined si no tiene un lugar propio.
const _DESTINOS_INGRESO: Record<string, string> = {
  acredita_salud: "/cuentas",
  tedef_web: "/lotes",
};
const _DESTINOS_TRABAJO: Record<string, string> = {
  ENVIAR_LOTE_SUSALUD: "/lotes",
  MONITOREAR_COMUNICACIONES_IAFAS: "/comunicaciones",
};

function destino_de_trabajo(aviso: Aviso): string | null | undefined {
  const trabajo = texto(aviso, "tipo_trabajo") ?? "";
  if (trabajo === "INICIAR_SESION_PLATAFORMA") {
    return _DESTINOS_INGRESO[texto(aviso, "plataforma") ?? ""] ?? null;
  }
  return _DESTINOS_TRABAJO[trabajo];
}

function destino_de(aviso: Aviso): string | null {
  if (aviso.tipo_evento.startsWith("CONTINGENCIA_")) return "/contingencias";
  if (aviso.tipo_evento === "CORREO_IAFAS_POR_REVISAR") return "/comunicaciones";
  if (aviso.tipo_evento.startsWith("SUSALUD_ENVIO_")) {
    const periodo = texto(aviso, "periodo");
    return periodo ? `/lotes?periodo=${periodo}` : "/lotes";
  }
  const de_trabajo = destino_de_trabajo(aviso);
  if (de_trabajo !== undefined) return de_trabajo;
  if (aviso.cuenta_medica_id) return `/cuentas/${aviso.cuenta_medica_id}`;
  if (aviso.lote_id) return `/lotes/${aviso.lote_id}`;
  return null;
}

function referencia_de(aviso: Aviso): string | null {
  const periodo = texto(aviso, "periodo");
  if (aviso.tipo_evento.startsWith("SUSALUD_ENVIO_") && periodo) return formatear_periodo(periodo);
  if (aviso.cuenta_medica_id) {
    return aviso.identificacion_interna ?? `Cuenta ${aviso.cuenta_medica_id}`;
  }
  if (aviso.lote_id) return `Lote ${aviso.numero_lote ?? aviso.lote_id}`;
  return null;
}

// "/lotes?periodo=202610" -> "/lotes".
function sin_consulta(destino: string): string {
  return destino.split("?")[0] ?? destino;
}

// El aviso se muestra igual; el enlace, solo si el usuario puede abrir
// el destino (el administrador recibe la ruptura de la cadena y el acceso
// denegado, pero no abre la cuenta).
export function describir_aviso(aviso: Aviso, roles: NombreRol[]): DescripcionAviso {
  const describir = _CATALOGO[aviso.tipo_evento.toLowerCase()];
  const base = describir ? describir(aviso) : { titulo: aviso.titulo, que_paso: "" };
  const destino = destino_de(aviso);
  return {
    ...base,
    destino: destino && ruta_permitida(sin_consulta(destino), roles) ? destino : null,
    referencia: referencia_de(aviso),
  };
}
