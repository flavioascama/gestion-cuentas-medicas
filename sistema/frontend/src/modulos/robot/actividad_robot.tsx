import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listar_actividad_robot, type ActividadRobot } from "../../api/robot";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { DialogoPasosRobot } from "./dialogo_pasos_robot";
import estilos from "./actividad_robot.module.css";

// Registro de lo que hizo el robot (2026-11-18): que tarea, a pedido de que
// usuario y a que hora. Solo lo ve el administrador, y sin imagenes: lo
// que el robot tiene en pantalla son datos del asegurado, que su rol no
// consulta.
const _TAREAS: Record<string, string> = {
  INICIAR_SESION_PLATAFORMA: "Inicio de sesión en la plataforma",
  CONSULTAR_COBERTURA: "Verificación de cobertura",
  CARGAR_LOTE_VALIDADOR: "Carga y validación del lote",
  ENVIAR_LOTE_SUSALUD: "Envío a SUSALUD",
};

const _COLUMNAS: ColumnaTabla<ActividadRobot>[] = [
  {
    clave: "tipo",
    encabezado: "Tarea del robot",
    formatear: (fila) => _TAREAS[fila.tipo] ?? fila.tipo,
  },
  { clave: "usuario", encabezado: "Usuario" },
  {
    clave: "iniciado_en",
    encabezado: "Fecha y hora",
    formatear: (fila) => formatear_fecha_hora(fila.iniciado_en),
  },
  {
    clave: "estado",
    encabezado: "Estado",
    formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
  },
  { clave: "pasos", encabezado: "Pasos", alinear_centro: true },
];

export function BandejaActividadRobot() {
  const [abierta, set_abierta] = useState<ActividadRobot | null>(null);
  const consulta = useQuery({
    queryKey: ["robot", "actividad"],
    queryFn: listar_actividad_robot,
    refetchInterval: 5000,
  });
  const filas = consulta.data ?? [];
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filas);

  return (
    <div className={estilos.panel}>
      <TituloPagina titulo="Actividad del robot" />
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="tareas"
      >
        <TablaDatos
          columnas={_COLUMNAS}
          filas={filas_pagina}
          obtener_clave={(fila) => fila.trabajo_id}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="No hay actividad del robot registrada."
          al_hacer_clic_fila={set_abierta}
        />
      </ConPaginacion>
      {abierta ? (
        <DialogoPasosRobot
          trabajo_id={abierta.trabajo_id}
          titulo={`${_TAREAS[abierta.tipo] ?? abierta.tipo} · ${abierta.usuario}`}
          al_cerrar={() => set_abierta(null)}
        />
      ) : null}
    </div>
  );
}
