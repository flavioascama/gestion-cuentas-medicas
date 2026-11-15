import type { DetalleCuenta as DetalleCuentaTipo } from "../../api/cuentas";
import { formatear_fecha } from "../../utilidades/formato";
import estilos from "./detalle_cuenta.module.css";

export function DatosCuenta({ cuenta }: { cuenta: DetalleCuentaTipo }) {
  const datos: { etiqueta: string; valor: string }[] = [
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
  ];

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Datos de la cuenta</div>
      <div className={estilos.rejilla}>
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
