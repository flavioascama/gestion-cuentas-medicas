import type { DetalleCuenta as DetalleCuentaTipo } from "../../api/cuentas";
import { formatear_fecha } from "../../utilidades/formato";
import { etiqueta_tipo_atencion } from "./etiquetas_atencion";
import estilos from "./detalle_cuenta.module.css";

type Dato = { etiqueta: string; valor: string };

// Solo las cuentas que vienen del sistema hospitalario; en una manual no
// se agrega nada.
function datos_de_atencion(cuenta: DetalleCuentaTipo): Dato[] {
  if (!cuenta.atencion_origen_id) return [];
  const datos: Dato[] = [
    { etiqueta: "Tipo de atención", valor: etiqueta_tipo_atencion(cuenta.tipo_atencion) },
    { etiqueta: "Atención de origen", valor: cuenta.atencion_origen_id },
  ];
  if (cuenta.nombre_medico) {
    const colegiatura = cuenta.colegiatura_medico ? ` (CMP ${cuenta.colegiatura_medico})` : "";
    datos.push({ etiqueta: "Médico tratante", valor: `${cuenta.nombre_medico}${colegiatura}` });
  }
  if (cuenta.diagnosticos_secundarios_cie10.length > 0) {
    datos.push({
      etiqueta: "Diagnósticos secundarios",
      valor: cuenta.diagnosticos_secundarios_cie10.join(", "),
    });
  }
  if (cuenta.fecha_ingreso_hospitalario) {
    const alta = cuenta.fecha_alta_hospitalaria
      ? formatear_fecha(cuenta.fecha_alta_hospitalaria)
      : "—";
    datos.push({
      etiqueta: "Hospitalización",
      valor: `${formatear_fecha(cuenta.fecha_ingreso_hospitalario)} al ${alta}`,
    });
  }
  return datos;
}

export function DatosCuenta({ cuenta }: { cuenta: DetalleCuentaTipo }) {
  const datos: Dato[] = [
    { etiqueta: "Identificación interna", valor: cuenta.identificacion_interna },
    { etiqueta: "Fecha de prestación", valor: formatear_fecha(cuenta.fecha_prestacion) },
    { etiqueta: "Hora de prestación", valor: cuenta.hora_prestacion },
    {
      etiqueta: "N.° historia clínica",
      valor: cuenta.datos_clinicos_reservados
        ? "Reservado"
        : (cuenta.numero_historia_clinica ?? "—"),
    },
    {
      etiqueta: "Diagnóstico principal (CIE-10)",
      valor: cuenta.datos_clinicos_reservados
        ? "Reservado"
        : (cuenta.diagnostico_principal_cie10 ?? "—"),
    },
    { etiqueta: "Asegurado", valor: `${cuenta.nombres_asegurado} ${cuenta.apellidos_asegurado}` },
    {
      etiqueta: "Documento del asegurado",
      valor: `${cuenta.tipo_documento_asegurado} ${cuenta.numero_documento_asegurado}`,
    },
    { etiqueta: "IAFAS", valor: cuenta.iafas_razon_social },
    ...datos_de_atencion(cuenta),
  ];

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Datos de la cuenta</div>
      <div className={estilos.rejilla_cuatro}>
        {datos.map((dato) => (
          <div key={dato.etiqueta} className={estilos.campo_dato}>
            <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
            <span className={estilos.valor_dato}>{dato.valor}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
