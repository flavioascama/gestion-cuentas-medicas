import type { ComunicacionIafas } from "../../api/comunicaciones_iafas";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { Boton } from "../../componentes_base/boton";
import { formatear_fecha_hora } from "../../utilidades/formato";

// Lo que la IAFAS comunico por su portal o por correo, como lo registro
// el robot de comunicaciones.

export const TIPOS_COMUNICACION: Record<string, string> = {
  AUDITORIA_CONFORME: "Conformidad de auditoría",
  OBSERVACION: "Observación",
  LIQUIDACION: "Liquidación",
  PAGO: "Aviso de pago",
};

export const CANALES_COMUNICACION: Record<string, string> = {
  PORTAL: "Portal de la IAFAS",
  CORREO: "Correo electrónico",
};

// Las comunicaciones guardadas antes del 2026-11-20 traen el texto de la
// excepcion: se muestran con una frase general.
const _TEXTO_TECNICO = /[_']|Tabla|Error|transicion|valido|terminal/;

export function detalle_no_aplicada(detalle: string): string {
  return _TEXTO_TECNICO.test(detalle) ? "La comunicación no se pudo aplicar a la cuenta." : detalle;
}

function resultado(fila: ComunicacionIafas): string {
  if (fila.resultado === "APLICADA") return "Aplicada";
  return fila.detalle ? `No aplicada: ${detalle_no_aplicada(fila.detalle)}` : "No aplicada";
}

// El contenido no va en la tabla: se lee en el mensaje original ("Ver").
export function columna_ver(
  al_ver: (fila: ComunicacionIafas) => void,
): ColumnaTabla<ComunicacionIafas> {
  return {
    clave: "codigo_iafas",
    encabezado: "",
    formatear: (fila) => (
      <Boton variante="terciario" onClick={() => al_ver(fila)}>
        Ver
      </Boton>
    ),
  };
}

export function crear_columnas_comunicaciones(): ColumnaTabla<ComunicacionIafas>[] {
  return [
    { clave: "codigo", encabezado: "Código" },
    {
      clave: "tipo",
      encabezado: "Comunicación",
      formatear: (fila) => TIPOS_COMUNICACION[fila.tipo] ?? fila.tipo,
    },
    {
      clave: "canal",
      encabezado: "Canal",
      formatear: (fila) => CANALES_COMUNICACION[fila.canal] ?? fila.canal,
    },
    {
      clave: "recibida_en",
      encabezado: "Recibida",
      formatear: (fila) => formatear_fecha_hora(fila.recibida_en),
    },
    { clave: "resultado", encabezado: "Registro", formatear: resultado },
    {
      clave: "respuesta_remitida_en",
      encabezado: "Respuesta entregada",
      formatear: (fila) =>
        fila.respuesta_remitida_en ? formatear_fecha_hora(fila.respuesta_remitida_en) : "—",
    },
  ];
}
