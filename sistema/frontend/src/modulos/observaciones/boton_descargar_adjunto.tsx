import { useMutation } from "@tanstack/react-query";
import { descargar_adjunto_respuesta, type Observacion } from "../../api/observaciones";
import { Boton } from "../../componentes_base/boton";
import { guardar_archivo } from "../../utilidades/archivo";

// El PDF que se adjuntó a la respuesta de la observación.
export function BotonDescargarAdjunto({ observacion }: { observacion: Observacion }) {
  const nombre = observacion.adjunto_nombre;
  const descarga = useMutation({
    mutationFn: () => descargar_adjunto_respuesta(observacion.id),
    onSuccess: (blob) => guardar_archivo(blob, nombre ?? "documento.pdf"),
  });
  if (!nombre) return null;
  return (
    <Boton variante="terciario" onClick={() => descarga.mutate()} disabled={descarga.isPending}>
      Documento adjunto
    </Boton>
  );
}
