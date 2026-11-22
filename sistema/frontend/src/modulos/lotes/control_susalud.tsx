import { useQuery } from "@tanstack/react-query";
import { listar_control_susalud, type ControlPeriodoSusalud } from "../../api/plazos";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_fecha_hora, formatear_periodo } from "../../utilidades/formato";
import {
  DeclaracionRegistrada,
  DeclaracionSinFacturacion,
  EnvioPeriodoSusalud,
} from "./accion_envio_susalud";

// RT-05 y RI-16: envio a SUSALUD dentro de los diez dias habiles del mes
// siguiente, por periodo, incluidos los meses sin lotes. Es el contenido
// de la pestana "Reporte mensual a SUSALUD" de la bandeja de lotes.
const _COLUMNAS: ColumnaTabla<ControlPeriodoSusalud>[] = [
  { clave: "periodo", encabezado: "Periodo", formatear: (fila) => formatear_periodo(fila.periodo) },
  { clave: "lotes", encabezado: "Lotes", alinear_centro: true },
  { clave: "pendientes_envio", encabezado: "Pendientes de envío", alinear_centro: true },
  {
    clave: "fecha_limite",
    encabezado: "Fecha límite",
    formatear: (fila) => formatear_fecha(fila.fecha_limite),
  },
  {
    clave: "ultimo_envio",
    encabezado: "Último envío",
    formatear: (fila) => (fila.ultimo_envio ? formatear_fecha_hora(fila.ultimo_envio) : "—"),
  },
  {
    clave: "estado",
    encabezado: "Estado",
    formatear: (fila) =>
      fila.declarada_en ? (
        <DeclaracionRegistrada fila={fila} />
      ) : (
        <EtiquetaEstado estado={fila.estado} />
      ),
  },
];

// Enviar el periodo o declarar el mes sin lotes es del analista; un periodo
// ya enviado o declarado no lleva boton.
function AccionPeriodo({ fila }: { fila: ControlPeriodoSusalud }) {
  if (fila.lotes === 0 && !fila.declarada_en) return <DeclaracionSinFacturacion fila={fila} />;
  if (fila.listos_envio > 0) {
    return <EnvioPeriodoSusalud periodo={fila.periodo} listos={fila.listos_envio} />;
  }
  if (fila.pendientes_envio > 0) return "Lotes sin remitir a la IAFAS";
  return null;
}

const _COLUMNA_ACCION: ColumnaTabla<ControlPeriodoSusalud> = {
  clave: "declarada_en",
  encabezado: "Acción",
  formatear: (fila) => <AccionPeriodo fila={fila} />,
};

export function ControlSusalud() {
  const { sesion } = usar_sesion();
  const acceso = Boolean(sesion?.roles.includes("analista") || sesion?.roles.includes("jefe"));
  const es_analista = Boolean(sesion?.roles.includes("analista"));
  const consulta = useQuery({
    queryKey: ["plazos", "susalud"],
    queryFn: listar_control_susalud,
    enabled: acceso,
  });

  if (!acceso) return null;

  return (
    <TablaDatos
      columnas={es_analista ? [..._COLUMNAS, _COLUMNA_ACCION] : _COLUMNAS}
      filas={consulta.data ?? []}
      obtener_clave={(fila) => fila.periodo}
      cargando={consulta.isPending}
      error={consulta.error}
      mensaje_vacio="No hay lotes generados."
    />
  );
}
