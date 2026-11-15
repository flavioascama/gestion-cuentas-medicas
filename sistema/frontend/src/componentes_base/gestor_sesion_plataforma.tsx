import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { solicitar_sesion_plataforma, type ResumenSesionPlataforma } from "../api/plataformas";
import { usar_sesion_vigente_plataforma } from "../modulos/plataformas/usar_sesiones_plataforma";
import { DialogoCaptcha } from "../modulos/plataformas/dialogo_captcha";
import { Boton } from "./boton";
import { EtiquetaEstado } from "./etiqueta_estado";
import { Mensaje } from "./mensaje";
import { MensajeErrorMutacion } from "./mensaje_error_mutacion";
import estilos from "./gestor_sesion_plataforma.module.css";

const _ESTADOS_ESPERANDO_CAPTCHA = new Set(["ESPERANDO_CAPTCHA", "CAPTCHA_RESPONDIDO"]);
const _ESTADOS_REINICIABLES = new Set(["FALLIDA", "EXPIRADA", "CERRADA"]);

interface Propiedades {
  plataforma: string;
  nombre_visible: string;
}

function FilaEstadoSesion({
  sesion_vigente,
  nombre_visible,
  al_reiniciar,
  reiniciando,
  al_responder_captcha,
}: {
  sesion_vigente: ResumenSesionPlataforma | undefined;
  nombre_visible: string;
  al_reiniciar: () => void;
  reiniciando: boolean;
  al_responder_captcha: () => void;
}) {
  const puede_reiniciar = !sesion_vigente || _ESTADOS_REINICIABLES.has(sesion_vigente.estado);
  const espera_captcha = Boolean(
    sesion_vigente && _ESTADOS_ESPERANDO_CAPTCHA.has(sesion_vigente.estado),
  );

  return (
    <div className={estilos.fila}>
      {sesion_vigente ? <EtiquetaEstado estado={sesion_vigente.estado} /> : null}
      {sesion_vigente?.motivo ? (
        <span className={estilos.motivo}>{sesion_vigente.motivo}</span>
      ) : null}
      {espera_captcha ? (
        <Boton variante="primario" onClick={al_responder_captcha}>
          Responder CAPTCHA
        </Boton>
      ) : puede_reiniciar ? (
        <Boton variante="primario" onClick={al_reiniciar} disabled={reiniciando}>
          Iniciar sesión con {nombre_visible}
        </Boton>
      ) : null}
    </div>
  );
}

// Reemplaza la antigua pantalla "Sesion con portales externos": la sesion
// asistida (login + CAPTCHA humano) se resuelve aqui mismo, en el punto del
// flujo de negocio que realmente la necesita (verificar cobertura, cargar
// en el validador), en vez de en una pantalla aparte sin relacion visible
// con la tarea que el usuario esta haciendo. No se muestra nada cuando la
// sesion ya esta activa, para no ensuciar la pantalla en el caso comun.
export function GestorSesionPlataforma({ plataforma, nombre_visible }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [mostrar_captcha, set_mostrar_captcha] = useState(false);
  const { consulta, sesion_vigente } = usar_sesion_vigente_plataforma(plataforma);

  const mutacion = useMutation({
    mutationFn: () => solicitar_sesion_plataforma(plataforma),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({
        queryKey: ["plataformas", "sesiones", plataforma],
      }),
  });

  if (consulta.isPending || sesion_vigente?.estado === "ACTIVA") return null;

  return (
    <div className={estilos.gestor}>
      <Mensaje
        tipo="advertencia"
        texto={`Se necesita una sesión con ${nombre_visible} para continuar.`}
      />
      <FilaEstadoSesion
        sesion_vigente={sesion_vigente}
        nombre_visible={nombre_visible}
        al_reiniciar={() => mutacion.mutate()}
        reiniciando={mutacion.isPending}
        al_responder_captcha={() => set_mostrar_captcha(true)}
      />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo solicitar la sesión."
      />
      {mostrar_captcha && sesion_vigente ? (
        <DialogoCaptcha
          sesion_id={sesion_vigente.id}
          plataforma={plataforma}
          al_cerrar={() => set_mostrar_captcha(false)}
        />
      ) : null}
    </div>
  );
}
