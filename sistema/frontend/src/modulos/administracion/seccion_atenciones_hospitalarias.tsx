import { useMutation } from "@tanstack/react-query";
import {
  cargar_atenciones_hospitalarias,
  descargar_plantilla_atenciones,
} from "../../api/atenciones_cargadas";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { guardar_archivo, leer_base64 } from "../../utilidades/archivo";
import { BotonCargarCatalogo } from "./boton_cargar_catalogo";
import estilos from "./administracion.module.css";

// Atenciones cerradas del sistema hospitalario, cargadas con un Excel:
// quedan disponibles en "Importar atención".
export function SeccionAtencionesHospitalarias() {
  const cargar = useMutation({
    mutationFn: async (archivo: File) =>
      cargar_atenciones_hospitalarias({
        nombre_archivo: archivo.name,
        contenido_base64: await leer_base64(archivo),
      }),
  });
  const plantilla = useMutation({
    mutationFn: descargar_plantilla_atenciones,
    onSuccess: (blob) => guardar_archivo(blob, "plantilla_atenciones.xlsx"),
  });
  return (
    <div className={estilos.seccion}>
      <div className={estilos.cabecera_seccion}>
        <div className={estilos.titulo_seccion}>Atenciones del sistema hospitalario</div>
        <Boton
          variante="terciario"
          onClick={() => plantilla.mutate()}
          disabled={plantilla.isPending}
        >
          Descargar plantilla
        </Boton>
        <BotonCargarCatalogo
          al_elegir={cargar.mutate}
          disabled={cargar.isPending}
          etiqueta="Cargar atenciones"
        />
      </div>
      <MensajeErrorMutacion
        error={cargar.error ?? plantilla.error}
        texto_por_defecto="No se pudo completar la operación."
      />
      {cargar.isSuccess ? (
        <Mensaje tipo="exito" texto={`Atenciones cargadas: ${cargar.data.cargadas}.`} />
      ) : null}
    </div>
  );
}
