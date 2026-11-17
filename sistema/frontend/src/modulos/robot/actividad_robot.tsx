import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listar_actividad_robot, type ActividadRobot } from "../../api/robot";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { DialogoNavegacionRobot } from "../../componentes_base/navegacion_robot";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "./actividad_robot.module.css";

// Trabajos del robot que dejaron capturas de su navegacion (2026-11-17):
// existen solo mientras el administrador tiene activa la opcion, y se
// borran a los siete dias.
const _TAREAS: Record<string, string> = {
  INICIAR_SESION_PLATAFORMA: "Inicio de sesión en la plataforma",
  CONSULTAR_COBERTURA: "Verificación de cobertura",
  CARGAR_LOTE_VALIDADOR: "Carga y validación del lote",
  ENVIAR_LOTE_SUSALUD: "Envío a SUSALUD",
};

const _ESTADOS_TERMINALES = new Set(["COMPLETADO", "AGOTADO"]);

const _COLUMNAS: ColumnaTabla<ActividadRobot>[] = [
  {
    clave: "tipo",
    encabezado: "Tarea del robot",
    formatear: (fila) => _TAREAS[fila.tipo] ?? fila.tipo,
  },
  {
    clave: "estado",
    encabezado: "Estado",
    formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
  },
  {
    clave: "iniciado_en",
    encabezado: "Inicio",
    formatear: (fila) => formatear_fecha_hora(fila.iniciado_en),
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
          mensaje_vacio="No hay navegación del robot registrada."
          al_hacer_clic_fila={set_abierta}
        />
      </ConPaginacion>
      {abierta ? (
        <DialogoNavegacionRobot
          trabajo_id={abierta.trabajo_id}
          en_curso={!_ESTADOS_TERMINALES.has(abierta.estado)}
          al_cerrar={() => set_abierta(null)}
        />
      ) : null}
    </div>
  );
}
