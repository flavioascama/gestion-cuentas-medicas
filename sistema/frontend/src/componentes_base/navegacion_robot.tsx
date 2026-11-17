// Navegacion del robot (2026-11-17): el robot trabaja en un navegador sin
// ventana, dentro del servidor. Si el administrador activo la opcion, cada
// paso deja una captura y aqui se ven en orden, mientras el trabajo avanza.
// Solo para el analista y el jefe: las capturas muestran datos del asegurado.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  consultar_navegacion_visible,
  listar_pasos_robot,
  obtener_captura_paso,
  type PasoRobot,
} from "../api/robot";
import { usar_sesion } from "../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../utilidades/formato";
import { Boton } from "./boton";
import { Dialogo } from "./dialogo";
import { MensajeVacio } from "./mensaje_vacio";
import estilos from "./navegacion_robot.module.css";

const _PLATAFORMAS: Record<string, string> = {
  acredita_salud: "ACREDITA SALUD",
  tedef_web: "TEDEF Web",
};

function nombre_plataforma(plataforma: string): string {
  return _PLATAFORMAS[plataforma] ?? plataforma;
}

function usar_puede_ver_navegacion(): boolean {
  const { sesion } = usar_sesion();
  return Boolean(sesion?.roles.includes("analista") || sesion?.roles.includes("jefe"));
}

function CapturaPaso({ trabajo_id, paso }: { trabajo_id: number; paso: PasoRobot }) {
  const consulta = useQuery({
    queryKey: ["robot", "captura", trabajo_id, paso.orden],
    queryFn: () => obtener_captura_paso(trabajo_id, paso.orden),
    staleTime: Infinity,
  });
  const [direccion, set_direccion] = useState<string | null>(null);

  useEffect(() => {
    if (!consulta.data) return;
    const temporal = URL.createObjectURL(consulta.data);
    set_direccion(temporal);
    return () => URL.revokeObjectURL(temporal);
  }, [consulta.data]);

  return (
    <figure className={estilos.captura}>
      <figcaption className={estilos.direccion}>{paso.url}</figcaption>
      {direccion ? (
        <img src={direccion} alt={`${nombre_plataforma(paso.plataforma)}: ${paso.descripcion}`} />
      ) : (
        <MensajeVacio texto={consulta.isError ? "No se pudo cargar la captura." : "Cargando…"} />
      )}
    </figure>
  );
}

function ListaPasos({
  pasos,
  elegido,
  al_elegir,
}: {
  pasos: PasoRobot[];
  elegido: number;
  al_elegir: (orden: number) => void;
}) {
  return (
    <ol className={estilos.pasos}>
      {pasos.map((paso) => (
        <li key={paso.orden}>
          <button
            type="button"
            className={`${estilos.paso} ${paso.orden === elegido ? estilos.paso_elegido : ""}`}
            aria-current={paso.orden === elegido ? "step" : undefined}
            onClick={() => al_elegir(paso.orden)}
          >
            <span className={estilos.numero}>{paso.orden}</span>
            <span>
              <span className={estilos.descripcion}>{paso.descripcion}</span>
              <span className={estilos.detalle}>
                {nombre_plataforma(paso.plataforma)} · {formatear_fecha_hora(paso.capturado_en)}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}

// Mientras nadie elige un paso, se muestra el ultimo: lo que el robot
// acaba de hacer.
function VisorNavegacionRobot({ trabajo_id, en_curso }: { trabajo_id: number; en_curso: boolean }) {
  const [elegido, set_elegido] = useState<number | null>(null);
  const consulta = useQuery({
    queryKey: ["robot", "pasos", trabajo_id],
    queryFn: () => listar_pasos_robot(trabajo_id),
    refetchInterval: en_curso ? 2000 : false,
  });
  const pasos = consulta.data ?? [];
  const actual = pasos.find((paso) => paso.orden === elegido) ?? pasos[pasos.length - 1];

  if (!actual) {
    return <MensajeVacio texto={en_curso ? "Esperando al robot…" : "Sin capturas del robot."} />;
  }
  return (
    <div className={estilos.visor}>
      <ListaPasos pasos={pasos} elegido={actual.orden} al_elegir={set_elegido} />
      <CapturaPaso trabajo_id={trabajo_id} paso={actual} />
    </div>
  );
}

export function DialogoNavegacionRobot({
  trabajo_id,
  en_curso,
  al_cerrar,
}: {
  trabajo_id: number;
  en_curso: boolean;
  al_cerrar: () => void;
}) {
  return (
    <Dialogo
      titulo="Navegación del robot"
      ancho="grande"
      al_cerrar={al_cerrar}
      acciones={
        <Boton variante="secundario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      <VisorNavegacionRobot trabajo_id={trabajo_id} en_curso={en_curso} />
    </Dialogo>
  );
}

// Boton junto al progreso de un trabajo. Solo aparece si el administrador
// activo la opcion y quien mira es el analista o el jefe.
export function BotonNavegacionRobot({
  trabajo_id,
  en_curso,
}: {
  trabajo_id: number;
  en_curso: boolean;
}) {
  const puede_ver = usar_puede_ver_navegacion();
  const [abierto, set_abierto] = useState(false);
  const opcion = useQuery({
    queryKey: ["robot", "navegacion-visible"],
    queryFn: consultar_navegacion_visible,
    enabled: puede_ver,
    staleTime: 60_000,
  });

  if (!puede_ver || !opcion.data?.activa) return null;
  return (
    <>
      <Boton variante="terciario" onClick={() => set_abierto(true)}>
        Ver navegación del robot
      </Boton>
      {abierto ? (
        <DialogoNavegacionRobot
          trabajo_id={trabajo_id}
          en_curso={en_curso}
          al_cerrar={() => set_abierto(false)}
        />
      ) : null}
    </>
  );
}
