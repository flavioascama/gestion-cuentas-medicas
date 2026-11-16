import type { Aviso } from "../../api/avisos";
import {
  CANALES_COMUNICACION,
  TIPOS_COMUNICACION,
} from "../comunicaciones/columnas_comunicaciones";
import { MOTIVOS_REVISION } from "../comunicaciones/etiquetas_correos";
import { formatear_fecha, formatear_fecha_hora } from "../../utilidades/formato";

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

const _TRABAJOS: Record<string, string> = {
  CONSULTAR_COBERTURA: "ACREDITA SALUD no respondió a la consulta de acreditación.",
  CARGAR_LOTE_VALIDADOR: "El validador TEDEF Web no respondió a la carga del lote.",
  MONITOREAR_RESPUESTA_IAFAS: "No llegó la respuesta de la IAFAS dentro de la ventana de espera.",
  ENVIAR_LOTE_SUSALUD: "No se completó el envío de los lotes del periodo a SUSALUD.",
  INICIAR_SESION_PLATAFORMA: "No se pudo iniciar la sesión asistida en una plataforma.",
  MONITOREAR_COMUNICACIONES_IAFAS: "No se pudo revisar el portal y el correo de la IAFAS.",
  ENVIAR_RESPUESTA_IAFAS: "No se pudo entregar la respuesta en el portal de la IAFAS.",
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
      que_paso: `Lotes del periodo sin enviar a SUSALUD; vence${limite ? ` el ${formatear_fecha(limite)}` : " pronto"}.`,
    };
  },
  susalud_envio_vencido_escalado: (a) => {
    const limite = texto(a, "fecha_limite");
    return {
      titulo: "Envío a SUSALUD vencido",
      que_paso: `Lotes del periodo sin enviar a SUSALUD${limite ? `; venció el ${formatear_fecha(limite)}` : ""}; escalado a la jefatura.`,
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
    const canal = CANALES_COMUNICACION[texto(a, "canal") ?? ""] ?? "";
    return {
      titulo: "Comunicación de la IAFAS no aplicada",
      que_paso: `${tipo} ${texto(a, "codigo") ?? ""} (${canal}): ${texto(a, "detalle") ?? ""}`,
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
    que_paso: `Intento sin permiso: ${texto(a, "metodo") ?? ""} ${texto(a, "ruta") ?? ""}. Plazo de comunicación a la autoridad: ${plazo_48_horas(a)}.`,
  }),
  contingencia_cobertura_registrada: (a) => ({
    titulo: "Acreditación registrada en contingencia",
    que_paso: texto(a, "sustento") ? `Sustento: ${texto(a, "sustento")}` : "Registro manual.",
  }),
  contingencia_validacion_registrada: (a) => ({
    titulo: "Validación registrada en contingencia",
    que_paso: texto(a, "sustento") ? `Sustento: ${texto(a, "sustento")}` : "Registro manual.",
  }),
  trabajo_agotado: (a) => ({
    titulo: "Falla del proceso de automatización",
    que_paso:
      _TRABAJOS[texto(a, "tipo_trabajo") ?? ""] ?? "Una tarea automática agotó sus reintentos.",
  }),
};

function destino_de(aviso: Aviso): string | null {
  if (aviso.tipo_evento.startsWith("CONTINGENCIA_")) return "/contingencias";
  if (aviso.tipo_evento === "CORREO_IAFAS_POR_REVISAR") return "/comunicaciones";
  const trabajo = texto(aviso, "tipo_trabajo");
  if (trabajo === "ENVIAR_LOTE_SUSALUD") return "/lotes";
  if (aviso.tipo_evento.startsWith("SUSALUD_ENVIO_")) return "/lotes";
  if (trabajo === "INICIAR_SESION_PLATAFORMA") return null;
  if (aviso.cuenta_medica_id) return `/cuentas/${aviso.cuenta_medica_id}`;
  if (aviso.lote_id) return `/lotes/${aviso.lote_id}`;
  return null;
}

function referencia_de(aviso: Aviso): string | null {
  const periodo = texto(aviso, "periodo");
  if (aviso.tipo_evento.startsWith("SUSALUD_ENVIO_") && periodo) return `Periodo ${periodo}`;
  if (aviso.cuenta_medica_id) {
    return aviso.identificacion_interna ?? `Cuenta ${aviso.cuenta_medica_id}`;
  }
  if (aviso.lote_id) return `Lote ${aviso.numero_lote ?? aviso.lote_id}`;
  return null;
}

export function describir_aviso(aviso: Aviso): DescripcionAviso {
  const describir = _CATALOGO[aviso.tipo_evento.toLowerCase()];
  const base = describir ? describir(aviso) : { titulo: aviso.titulo, que_paso: "" };
  return { ...base, destino: destino_de(aviso), referencia: referencia_de(aviso) };
}
