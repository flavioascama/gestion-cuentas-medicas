import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { solicitar_sesion_plataforma } from "../../api/plataformas";
import { DialogoCaptcha } from "./dialogo_captcha";
import { usar_sesion_vigente_plataforma } from "./usar_sesiones_plataforma";

const _PIDE_CODIGO = "ESPERANDO_CAPTCHA";
const _REINICIABLES = new Set(["FALLIDA", "EXPIRADA", "CERRADA"]);
// Sesiones que se piden solas antes de avisar que no hay conexion.
const _MAXIMO_PEDIDOS = 2;

interface SesionAutomatica {
  // El dialogo del codigo de verificacion, cuando la plataforma lo pide.
  dialogo: ReactNode;
  // La plataforma pide el codigo y la persona cerro el dialogo sin responder.
  espera_codigo: boolean;
  abrir_codigo: () => void;
  // Se pidio la sesion varias veces y la plataforma no la acepto.
  sin_conexion: boolean;
  reintentar: () => void;
}

// Pide una sesion nueva, sola, mientras haga falta y no haya una vigente.
function usar_pedido_de_sesion(plataforma: string, necesita: boolean) {
  const cliente_consultas = useQueryClient();
  const { consulta, sesion_vigente } = usar_sesion_vigente_plataforma(plataforma);
  const [pedidos, set_pedidos] = useState(0);
  const en_vuelo = useRef(false);
  const pedido = useMutation({
    mutationFn: () => solicitar_sesion_plataforma(plataforma),
    onSettled: async () => {
      await cliente_consultas.invalidateQueries({
        queryKey: ["plataformas", "sesiones", plataforma],
      });
      en_vuelo.current = false;
    },
  });
  const pedir = pedido.mutate;
  const sin_sesion = !sesion_vigente || _REINICIABLES.has(sesion_vigente.estado);
  const falta = necesita && sin_sesion && !consulta.isFetching && !pedido.isPending;
  const puede_pedir = falta && pedidos < _MAXIMO_PEDIDOS;

  useEffect(() => {
    if (!puede_pedir || en_vuelo.current) return;
    en_vuelo.current = true;
    set_pedidos((anteriores) => anteriores + 1);
    pedir();
  }, [puede_pedir, pedir]);

  return {
    sesion_vigente,
    sin_conexion: falta && pedidos >= _MAXIMO_PEDIDOS,
    reintentar: () => set_pedidos(0),
  };
}

// Cuando la plataforma pide el codigo, el dialogo se abre solo. Si la persona
// lo cierra sin responder, no vuelve a abrirse para esa sesion. Tras
// responder se oculta hasta que la plataforma conteste; si vuelve a pedir el
// codigo (respuesta equivocada), se abre otra vez.
function usar_dialogo_de_codigo(sesion_que_pide: number | null) {
  const [descartada, set_descartada] = useState<number | null>(null);
  const [respondida, set_respondida] = useState<number | null>(null);

  if (respondida !== null && sesion_que_pide === null) set_respondida(null);

  const abierto =
    sesion_que_pide !== null && sesion_que_pide !== descartada && sesion_que_pide !== respondida;
  return {
    abierto,
    espera_codigo: sesion_que_pide !== null && sesion_que_pide === descartada,
    descartar: () => set_descartada(sesion_que_pide),
    responder: () => set_respondida(sesion_que_pide),
    abrir_codigo: () => set_descartada(null),
  };
}

// La sesion con la plataforma se maneja sola (pedido del usuario, 2026-11-18).
// Mientras una tarea la necesita (`necesita`), si no hay sesion vigente se
// pide una; lo unico que la persona ve es el codigo de verificacion (CAPTCHA),
// que la plataforma exige que responda una persona.
export function usar_sesion_automatica(plataforma: string, necesita: boolean): SesionAutomatica {
  const { sesion_vigente, sin_conexion, reintentar } = usar_pedido_de_sesion(plataforma, necesita);
  const pide_codigo = necesita && sesion_vigente?.estado === _PIDE_CODIGO;
  const sesion_que_pide = pide_codigo && sesion_vigente ? sesion_vigente.id : null;
  const codigo = usar_dialogo_de_codigo(sesion_que_pide);
  return {
    dialogo:
      codigo.abierto && sesion_que_pide !== null ? (
        <DialogoCaptcha
          sesion_id={sesion_que_pide}
          plataforma={plataforma}
          al_cerrar={codigo.descartar}
          al_responder={codigo.responder}
        />
      ) : null,
    espera_codigo: codigo.espera_codigo,
    abrir_codigo: codigo.abrir_codigo,
    sin_conexion,
    reintentar,
  };
}
