import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { obtener_trabajo, type DetalleTrabajo } from "../api/trabajos";
import { formatear_duracion } from "../utilidades/formato";
import { resolver_estado } from "./mapa_estados";
import { BotonNavegacionRobot } from "./navegacion_robot";

// REQUIERE_SESION no es terminal: en cuanto el usuario resuelve la sesion
// asistida (GestorSesionPlataforma), el backend reactiva este mismo trabajo
// a PENDIENTE por su cuenta (IniciarSesionPlataforma.ejecutar ->
// reactivar_requieren_sesion) sin que nadie vuelva a pulsar el boton de
// aqui. Si se dejara de sondear en REQUIERE_SESION, como antes, la tarjeta
// se quedaria mostrando "Requiere sesion" para siempre aunque el trabajo ya
// haya terminado en el servidor -- un punto muerto visual real, no solo de
// apariencia, porque `al_completar` (que invalida la completitud de la
// cuenta) tampoco llegaria a dispararse.
const _ESTADOS_TERMINALES = new Set(["COMPLETADO", "AGOTADO"]);
// Trabajos que el robot hace con su navegador: solo esos pueden mostrar
// su navegacion (los de correo y de consulta por programa no la tienen).
const _TIPOS_CON_NAVEGADOR = new Set([
  "INICIAR_SESION_PLATAFORMA",
  "CONSULTAR_COBERTURA",
  "CARGAR_LOTE_VALIDADOR",
  "ENVIAR_LOTE_SUSALUD",
]);

interface Propiedades {
  trabajo_id: number;
  al_completar?: (trabajo: DetalleTrabajo) => void;
}

export function ProgresoTrabajo({ trabajo_id, al_completar }: Propiedades) {
  const [ahora, set_ahora] = useState(() => Date.now());

  const consulta = useQuery({
    queryKey: ["trabajo", trabajo_id],
    queryFn: () => obtener_trabajo(trabajo_id),
    refetchInterval: (query) =>
      _ESTADOS_TERMINALES.has(query.state.data?.estado ?? "") ? false : 1500,
  });

  useEffect(() => {
    const intervalo = setInterval(() => set_ahora(Date.now()), 1000);
    return () => clearInterval(intervalo);
  }, []);

  useEffect(() => {
    if (consulta.data && consulta.data.estado === "COMPLETADO") al_completar?.(consulta.data);
  }, [consulta.data, al_completar]);

  if (consulta.isPending) return <span>Consultando el estado del trabajo…</span>;
  if (consulta.isError) return <span>No se pudo consultar el trabajo.</span>;

  const trabajo = consulta.data;
  const transcurrido = formatear_duracion((ahora - new Date(trabajo.creado_en).getTime()) / 1000);
  const definicion = resolver_estado(trabajo.estado);

  return (
    <span>
      {definicion.texto}, {transcurrido}
      {trabajo.error ? ` — ${trabajo.error}` : ""}
      {_TIPOS_CON_NAVEGADOR.has(trabajo.tipo) ? (
        <>
          {" "}
          <BotonNavegacionRobot
            trabajo_id={trabajo_id}
            en_curso={!_ESTADOS_TERMINALES.has(trabajo.estado)}
          />
        </>
      ) : null}
    </span>
  );
}
