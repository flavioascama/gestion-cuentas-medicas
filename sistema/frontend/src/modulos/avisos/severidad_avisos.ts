import type { Aviso } from "../../api/avisos";
import { IconoAtendido, IconoCritico, IconoEscalamiento, IconoPorVencer } from "./iconos_avisos";

export const ETIQUETA_SEVERIDAD: Record<string, string> = {
  critico: "Crítico",
  escalamiento: "Vencido",
  aviso: "Por vencer",
  informativo: "Aviso",
};

// Avisos que no son un vencimiento: no se cuentan en "Por vencer".
const _INFORMATIVOS = new Set([
  "OBSERVACION_REASIGNADA",
  "ACCESO_DENEGADO",
  "CONTINGENCIA_COBERTURA_REGISTRADA",
  "CONTINGENCIA_VALIDACION_REGISTRADA",
  "ANULACION",
  "ANULACION_RECHAZADA",
]);

export function tipo_aviso(aviso: Aviso): string {
  return _INFORMATIVOS.has(aviso.tipo_evento) ? "informativo" : aviso.severidad;
}

export function icono_severidad(severidad: string, atendido: boolean) {
  if (atendido) return IconoAtendido;
  if (severidad === "critico") return IconoCritico;
  if (severidad === "escalamiento") return IconoEscalamiento;
  return IconoPorVencer;
}
