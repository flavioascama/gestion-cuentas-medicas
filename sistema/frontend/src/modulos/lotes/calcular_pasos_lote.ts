import type { PasoLinea } from "../../componentes_base/linea_estados_lote";
import type {
  DetalleLote,
  InformePrevalidacion,
  ResultadoValidacionOficial,
  ResumenAcuse,
} from "../../api/lotes";
import { formatear_fecha_hora } from "../../utilidades/formato";

// Un lote solo llega a tener id/detalle si su prevalidacion fue
// conforme (GenerarLote no persiste lotes no conformes), por eso
// ausencia de informe persistido (lotes previos a la Fase 18) se trata
// como "completado sin fecha registrada", no como un paso pendiente.
function calcular_paso_prevalidacion(
  prevalidacion: InformePrevalidacion | undefined,
  prevalidacion_no_encontrada: boolean,
): PasoLinea {
  if (prevalidacion) {
    return {
      etiqueta: "Prevalidación",
      estado: prevalidacion.conforme ? "completado" : "error",
      fecha_hora: formatear_fecha_hora(prevalidacion.generado_en),
    };
  }
  return {
    etiqueta: "Prevalidación",
    estado: prevalidacion_no_encontrada ? "completado" : "pendiente",
  };
}

function calcular_paso_validacion(validaciones: ResultadoValidacionOficial[]): PasoLinea {
  const detallada = validaciones.find((v) => v.etapa === "DETALLADA");
  const forma = validaciones.find((v) => v.etapa === "FORMA");
  const referencia = detallada ?? forma;
  const estado = validaciones.some((v) => v.resultado === "OBSERVADO")
    ? "error"
    : detallada
      ? "completado"
      : forma
        ? "actual"
        : "pendiente";
  return {
    etiqueta: "Validación oficial",
    estado,
    fecha_hora: referencia ? formatear_fecha_hora(referencia.registrado_en) : undefined,
  };
}

function calcular_paso_archivo(lote: DetalleLote): PasoLinea {
  return {
    etiqueta: "Archivo de transmisión",
    estado: lote.s01_obtenido_en ? "completado" : "pendiente",
    fecha_hora: lote.s01_obtenido_en ? formatear_fecha_hora(lote.s01_obtenido_en) : undefined,
  };
}

function calcular_paso_remision(acuses: ResumenAcuse[]): PasoLinea {
  const enviado = acuses.find((a) => a.resultado_transferencia === "ENVIADO");
  const con_error = acuses.find((a) => a.resultado_transferencia === "ERROR_TRANSFERENCIA");
  const referencia = enviado ?? con_error;
  return {
    etiqueta: "Remisión a la IAFAS",
    estado: enviado ? "completado" : con_error ? "error" : "pendiente",
    fecha_hora: referencia ? formatear_fecha_hora(referencia.intentado_en) : undefined,
  };
}

function calcular_paso_respuesta(acuses: ResumenAcuse[]): PasoLinea {
  const respondido = acuses.find((a) => a.respuesta_receptor !== null);
  return {
    etiqueta: "Respuesta de la IAFAS",
    estado: respondido
      ? respondido.respuesta_receptor === "ACEPTADO"
        ? "completado"
        : "error"
      : "pendiente",
    fecha_hora:
      respondido?.respondido_en != null
        ? formatear_fecha_hora(respondido.respondido_en)
        : undefined,
  };
}

function calcular_paso_susalud(lote: DetalleLote): PasoLinea {
  return {
    etiqueta: "Envío a SUSALUD",
    estado: lote.enviado_susalud_en ? "completado" : "pendiente",
    fecha_hora: lote.enviado_susalud_en ? formatear_fecha_hora(lote.enviado_susalud_en) : undefined,
  };
}

// Seccion 12, pantalla 6: los seis pasos del flujo de un lote (Seccion 7
// del plan v3), uno por funcion para no repetir la logica de "estado +
// fecha" de cada paso en un solo bloque.
export function calcular_pasos_lote(
  lote: DetalleLote,
  prevalidacion: InformePrevalidacion | undefined,
  prevalidacion_no_encontrada: boolean,
  validaciones: ResultadoValidacionOficial[],
  acuses: ResumenAcuse[],
): PasoLinea[] {
  return [
    calcular_paso_prevalidacion(prevalidacion, prevalidacion_no_encontrada),
    calcular_paso_validacion(validaciones),
    calcular_paso_archivo(lote),
    calcular_paso_remision(acuses),
    calcular_paso_respuesta(acuses),
    calcular_paso_susalud(lote),
  ];
}
