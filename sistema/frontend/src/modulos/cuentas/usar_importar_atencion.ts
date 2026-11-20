import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  importar_archivo,
  importar_atencion,
  listar_atenciones,
  type ResumenAtencion,
} from "../../api/atenciones";
import { ErrorApi } from "../../api/cliente_http";
import { listar_iafas } from "../../api/iafas";

type Origen = { atencion_id: string } | { archivo: File };

async function importar(origen: Origen): Promise<{ cuenta_id: number }> {
  if ("atencion_id" in origen) return importar_atencion(origen.atencion_id);
  let contenido: unknown;
  try {
    contenido = JSON.parse(await origen.archivo.text());
  } catch {
    throw new ErrorApi("ARCHIVO_INVALIDO", "El archivo no es un .json válido.", 0, {});
  }
  return importar_archivo(contenido);
}

// Una atencion ya importada lleva a la cuenta que ya existe.
function cuenta_existente(error: unknown): number | null {
  if (!(error instanceof ErrorApi) || error.codigo !== "ATENCION_YA_IMPORTADA") return null;
  const cuenta_id = Number(error.detalles.cuenta_id);
  return Number.isInteger(cuenta_id) && cuenta_id > 0 ? cuenta_id : null;
}

export function coincide_atencion(atencion: ResumenAtencion, busqueda: string): boolean {
  const objetivo = busqueda.trim().toLowerCase();
  if (!objetivo) return true;
  const { numero_documento, nombres, apellidos } = atencion.paciente;
  return (
    numero_documento.toLowerCase().includes(objetivo) ||
    `${nombres} ${apellidos}`.toLowerCase().includes(objetivo)
  );
}

export function usar_importar_atencion(al_importar: (cuenta_id: number) => void) {
  const cliente_consultas = useQueryClient();
  const [busqueda, set_busqueda] = useState("");
  const atenciones = useQuery({
    queryKey: ["atenciones-hospitalarias"],
    queryFn: listar_atenciones,
  });
  const iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });

  const mutacion = useMutation({
    mutationFn: importar,
    onSuccess: (respuesta) => {
      void cliente_consultas.invalidateQueries({ queryKey: ["atenciones-hospitalarias"] });
      al_importar(respuesta.cuenta_id);
    },
    onError: (error) => {
      const cuenta_id = cuenta_existente(error);
      if (cuenta_id) al_importar(cuenta_id);
    },
  });

  const nombre_iafas = (codigo: string) =>
    iafas.data?.find((iafa) => iafa.codigo === codigo)?.razon_social ?? codigo;
  const filas = (atenciones.data ?? []).filter((fila) => coincide_atencion(fila, busqueda));
  return { atenciones, filas, busqueda, set_busqueda, mutacion, nombre_iafas };
}
