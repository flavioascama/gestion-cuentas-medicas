import type { Vencimiento } from "../../api/plazos";
import { formatear_fecha } from "../../utilidades/formato";
import estilos from "./plazo_cuenta.module.css";

// RNF-06: el plazo vigente de cada cuenta, junto a su estado, en la
// bandeja y en el detalle (el mismo que dispara avisos y escalamientos).

const _HITOS: Record<string, string> = {
  OBSERVACION: "Respuesta a la IAFAS",
  REENVIO: "Reenvío",
  AUDITORIA: "Auditoría IAFAS",
  PAGO: "Pago IAFAS",
  COBERTURA: "Vigencia de cobertura",
};

export function PlazoCuenta({ vencimiento }: { vencimiento: Vencimiento | undefined }) {
  if (!vencimiento) return <span className={estilos.sin_plazo}>—</span>;
  const tono = vencimiento.vencido
    ? estilos.vencido
    : vencimiento.por_vencer
      ? estilos.por_vencer
      : "";
  return (
    <span className={`${estilos.plazo} ${tono}`}>
      <span className={estilos.fecha}>
        {vencimiento.vencido ? "Vencido " : ""}
        {formatear_fecha(vencimiento.vence_en)}
      </span>
      <span className={estilos.hito}>{_HITOS[vencimiento.hito] ?? vencimiento.hito}</span>
    </span>
  );
}
