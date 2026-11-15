import { IconoAtendido, IconoCritico, IconoEscalamiento, IconoPorVencer } from "./iconos_avisos";

export const ETIQUETA_SEVERIDAD: Record<string, string> = {
  critico: "Crítico",
  escalamiento: "Vencido",
  aviso: "Por vencer",
};

export function icono_severidad(severidad: string, atendido: boolean) {
  if (atendido) return IconoAtendido;
  if (severidad === "critico") return IconoCritico;
  if (severidad === "escalamiento") return IconoEscalamiento;
  return IconoPorVencer;
}
