import { useQuery } from "@tanstack/react-query";
import { listar_control_susalud, type ControlPeriodoSusalud } from "../../api/plazos";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";

// RT-05 y RI-16: envio a SUSALUD dentro de los diez dias habiles del mes
// siguiente, por periodo, incluidos los meses sin lotes.
const _COLUMNAS: ColumnaTabla<ControlPeriodoSusalud>[] = [
  { clave: "periodo", encabezado: "Periodo" },
  { clave: "lotes", encabezado: "Lotes", alinear_centro: true },
  { clave: "pendientes_envio", encabezado: "Pendientes de envío", alinear_centro: true },
  {
    clave: "fecha_limite",
    encabezado: "Fecha límite",
    formatear: (fila) => formatear_fecha(fila.fecha_limite),
  },
  {
    clave: "ultimo_envio",
    encabezado: "Enviado",
    formatear: (fila) => (fila.ultimo_envio ? formatear_fecha_hora(fila.ultimo_envio) : "—"),
  },
  {
    clave: "estado",
    encabezado: "Estado",
    formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
  },
];

export function ControlSusalud() {
  const { sesion } = usar_sesion();
  const acceso = Boolean(sesion?.roles.includes("analista") || sesion?.roles.includes("jefe"));
  const consulta = useQuery({
    queryKey: ["plazos", "susalud"],
    queryFn: listar_control_susalud,
    enabled: acceso,
  });

  if (!acceso) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Envío a SUSALUD</div>
      <TablaDatos
        columnas={_COLUMNAS}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.periodo}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay lotes generados."
      />
    </div>
  );
}
