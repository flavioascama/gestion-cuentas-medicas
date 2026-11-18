import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cambiar_navegacion_visible,
  consultar_navegacion_visible,
  type EstadoNavegacion,
  type ModoNavegacion,
} from "../../api/robot";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";
import estilos from "./administracion.module.css";

// El administrador decide si el trabajo del robot se ve y donde (2026-11-18):
// en la ventana del navegador, cuando hay un robot encendido en un equipo con
// pantalla (uso local), o dentro del sistema, cuando corre en un servidor
// (uso desplegado). El solo lo activa: no ve los datos del asegurado.
const _MODOS: { valor: ModoNavegacion; etiqueta: string }[] = [
  { valor: "ventana", etiqueta: "Local: ventana del navegador en el equipo del robot" },
  { valor: "sistema", etiqueta: "Desplegado: ventana dentro del sistema" },
];
const _POR_DEFECTO: EstadoNavegacion = {
  activa: false,
  modo: "sistema",
  robot_con_pantalla: false,
};

// Solo se puede ver la ventana real si hay un robot encendido en un equipo
// con pantalla (sistema/automatizacion/ejecutar_con_ventana.ps1).
function RobotConVentana({ encendido }: { encendido: boolean }) {
  return (
    <div className={estilos.opcion}>
      <span>Robot con ventana en este equipo</span>
      <EtiquetaEstado estado={encendido ? "ROBOT_ENCENDIDO" : "ROBOT_APAGADO"} />
    </div>
  );
}

export function OpcionNavegacionRobot() {
  const cliente_consultas = useQueryClient();
  const consulta = useQuery({
    queryKey: ["robot", "navegacion-visible"],
    queryFn: consultar_navegacion_visible,
    // Para ver al momento si el robot con ventana se enciende o se apaga.
    refetchInterval: 5000,
  });
  const estado = consulta.data ?? _POR_DEFECTO;
  const cambio = useMutation({
    mutationFn: cambiar_navegacion_visible,
    onSuccess: (nuevo) => cliente_consultas.setQueryData(["robot", "navegacion-visible"], nuevo),
  });
  const ocupado = consulta.isPending || cambio.isPending;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Robot</div>
      <div className={estilos.opcion}>
        <span>Trabajo del robot visible</span>
        <EtiquetaEstado estado={estado.activa ? "OPCION_ACTIVADA" : "OPCION_DESACTIVADA"} />
        <Boton
          variante="secundario"
          onClick={() => cambio.mutate({ activa: !estado.activa, modo: estado.modo })}
          disabled={ocupado}
        >
          {estado.activa ? "Desactivar" : "Activar"}
        </Boton>
      </div>
      <div className={estilos.opcion_modo}>
        <Selector
          etiqueta="Dónde corre el sistema"
          opciones={_MODOS}
          value={estado.modo}
          disabled={ocupado}
          onChange={(evento) =>
            cambio.mutate({ activa: estado.activa, modo: evento.target.value as ModoNavegacion })
          }
        />
      </div>
      {estado.modo === "ventana" ? <RobotConVentana encendido={estado.robot_con_pantalla} /> : null}
      <MensajeErrorMutacion
        error={cambio.error}
        texto_por_defecto="No se pudo cambiar la opción."
      />
    </div>
  );
}
