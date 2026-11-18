// Robot en vivo. Cuando el robot corre en un servidor sin pantalla (uso
// desplegado) y el administrador activo que su trabajo se vea, quien pidio
// una tarea ve aqui lo que el navegador del robot muestra mientras la hace.
// Sin ningun adorno (pedido del usuario, 2026-11-18): solo la pantalla del
// robot, que aparece al empezar y se va al terminar. Nada queda guardado.
// En uso local el robot abre su propia ventana y esto no aparece.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  consultar_navegacion_visible,
  consultar_robot_en_vivo,
  obtener_cuadro_en_vivo,
  type TrabajoEnVivo,
} from "../api/robot";
import { usar_sesion } from "../sesion/contexto_sesion";
import estilos from "./robot_en_vivo.module.css";

const _MS_ENTRE_CUADROS = 350;
// Al terminar, el ultimo cuadro queda a la vista este tiempo.
const _MS_AL_TERMINAR = 3000;

function esperar(milisegundos: number): Promise<void> {
  return new Promise((resolver) => setTimeout(resolver, milisegundos));
}

function usar_trabajo_en_vivo(): TrabajoEnVivo | null {
  const { sesion } = usar_sesion();
  const opera = Boolean(sesion?.roles.includes("analista") || sesion?.roles.includes("jefe"));
  const opcion = useQuery({
    queryKey: ["robot", "navegacion-visible"],
    queryFn: consultar_navegacion_visible,
    enabled: opera,
    refetchInterval: 30_000,
  });
  const en_vivo = useQuery({
    queryKey: ["robot", "en-vivo"],
    queryFn: consultar_robot_en_vivo,
    enabled: opera && Boolean(opcion.data?.activa),
    refetchInterval: 1500,
  });
  return en_vivo.data ?? null;
}

// El trabajo que se muestra: el que esta en vivo y, cuando termina, el mismo
// unos segundos mas. Quien lo cierra no vuelve a verlo por ese trabajo.
function usar_trabajo_mostrado(en_vivo: TrabajoEnVivo | null) {
  const [mostrado, set_mostrado] = useState<TrabajoEnVivo | null>(null);
  const [cerrado, set_cerrado] = useState<number | null>(null);

  useEffect(() => {
    if (en_vivo) {
      set_mostrado(en_vivo);
      return;
    }
    const espera = setTimeout(() => set_mostrado(null), _MS_AL_TERMINAR);
    return () => clearTimeout(espera);
  }, [en_vivo]);

  const visible = mostrado && mostrado.trabajo_id !== cerrado ? mostrado : null;
  return { visible, cerrar: () => set_cerrado(mostrado?.trabajo_id ?? null) };
}

// Pide el cuadro del trabajo una y otra vez mientras siga en curso; al
// terminar conserva el ultimo que recibio.
function usar_cuadro(trabajo_id: number | null, en_curso: boolean): string | null {
  const [direccion, set_direccion] = useState<string | null>(null);
  const actual = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (actual.current) URL.revokeObjectURL(actual.current);
      actual.current = null;
      set_direccion(null);
    };
  }, [trabajo_id]);

  useEffect(() => {
    if (trabajo_id === null || !en_curso) return;
    let vigente = true;
    let primera = true;
    async function pedir(id: number): Promise<void> {
      while (vigente) {
        try {
          const imagen = await obtener_cuadro_en_vivo(id, primera);
          primera = false;
          if (!vigente) return;
          const nueva = URL.createObjectURL(imagen);
          if (actual.current) URL.revokeObjectURL(actual.current);
          actual.current = nueva;
          set_direccion(nueva);
        } catch {
          // Sin cuadro por ahora: el robot aun no abre la pagina o ya termino.
        }
        await esperar(_MS_ENTRE_CUADROS);
      }
    }
    void pedir(trabajo_id);
    return () => {
      vigente = false;
    };
  }, [trabajo_id, en_curso]);

  return direccion;
}

export function RobotEnVivo() {
  const en_vivo = usar_trabajo_en_vivo();
  const { visible, cerrar } = usar_trabajo_mostrado(en_vivo);
  const imagen = usar_cuadro(visible?.trabajo_id ?? null, en_vivo !== null);

  if (!visible || !imagen) return null;
  return (
    <div className={estilos.ventana}>
      <img className={estilos.pantalla} src={imagen} alt="Navegador del robot" />
      <button type="button" className={estilos.cerrar} onClick={cerrar} aria-label="Cerrar">
        ×
      </button>
    </div>
  );
}
