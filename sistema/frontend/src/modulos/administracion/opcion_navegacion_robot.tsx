import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cambiar_navegacion_visible, consultar_navegacion_visible } from "../../api/robot";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import estilos from "./administracion.module.css";

// El administrador activa o apaga que el robot guarde una captura de cada
// paso (2026-11-17). Solo la activa: las capturas las ven el analista y el
// jefe, que ya trabajan con los datos del asegurado.
export function OpcionNavegacionRobot() {
  const cliente_consultas = useQueryClient();
  const consulta = useQuery({
    queryKey: ["robot", "navegacion-visible"],
    queryFn: consultar_navegacion_visible,
  });
  const activa = consulta.data?.activa ?? false;
  const cambio = useMutation({
    mutationFn: () => cambiar_navegacion_visible(!activa),
    onSuccess: (opcion) => cliente_consultas.setQueryData(["robot", "navegacion-visible"], opcion),
  });

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Robot</div>
      <div className={estilos.opcion}>
        <span>Navegación del robot visible para el analista y el jefe</span>
        <EtiquetaEstado estado={activa ? "OPCION_ACTIVADA" : "OPCION_DESACTIVADA"} />
        <Boton
          variante="secundario"
          onClick={() => cambio.mutate()}
          disabled={consulta.isPending || cambio.isPending}
        >
          {activa ? "Desactivar" : "Activar"}
        </Boton>
      </div>
      <MensajeErrorMutacion
        error={cambio.error}
        texto_por_defecto="No se pudo cambiar la opción."
      />
    </div>
  );
}
