import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { actualizar_parametros_sistema, listar_parametros_sistema } from "../../api/parametros";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { OpcionNavegacionRobot } from "./opcion_navegacion_robot";
import estilos from "./administracion.module.css";

// Parametros del sistema, con nombres y unidades legibles agrupados por
// tema, en vez de las claves de configuracion (rediseno de la
// administracion, 2026-11-15). El administrador los cambia por grupo.
interface DefinicionParametro {
  etiqueta: string;
  unidad: string;
}

const _CLAVE_CONSULTA = ["administracion", "parametros", "sistema"];

const _DEFINICIONES = new Map<string, DefinicionParametro>([
  ["DURACION_SESION_MINUTOS", { etiqueta: "Duración de la sesión", unidad: "minutos" }],
  [
    "MAXIMO_INTENTOS_FALLIDOS_SESION",
    { etiqueta: "Intentos fallidos antes del bloqueo", unidad: "intentos" },
  ],
  ["DURACION_BLOQUEO_SESION_MINUTOS", { etiqueta: "Duración del bloqueo", unidad: "minutos" }],
  [
    "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO",
    { etiqueta: "Plazo para reenviar un lote rechazado", unidad: "días" },
  ],
  [
    "DIAS_AVISO_PREVIO_VENCIMIENTO",
    { etiqueta: "Aviso antes del vencimiento de un plazo", unidad: "días" },
  ],
  [
    "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA",
    { etiqueta: "Aviso antes del fin de vigencia de la carta de garantía", unidad: "días" },
  ],
  [
    "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS",
    { etiqueta: "Revisión de vencimientos", unidad: "minutos" },
  ],
  [
    "TEMPORIZADOR_INTERVALO_CADENA_HORAS",
    { etiqueta: "Verificación de la integridad del historial", unidad: "horas" },
  ],
  ["FERIADOS", { etiqueta: "Feriados", unidad: "AAAA-MM-DD, separados por comas" }],
]);

interface Grupo {
  titulo: string;
  claves: string[];
}

const _GRUPOS: Grupo[] = [
  {
    titulo: "Acceso y sesión",
    claves: [
      "DURACION_SESION_MINUTOS",
      "MAXIMO_INTENTOS_FALLIDOS_SESION",
      "DURACION_BLOQUEO_SESION_MINUTOS",
    ],
  },
  {
    titulo: "Plazos y avisos",
    claves: [
      "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO",
      "DIAS_AVISO_PREVIO_VENCIMIENTO",
      "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA",
    ],
  },
  {
    titulo: "Revisiones automáticas",
    claves: ["TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS", "TEMPORIZADOR_INTERVALO_CADENA_HORAS"],
  },
  { titulo: "Calendario", claves: ["FERIADOS"] },
];

function CampoParametro({
  clave,
  valor,
  cargando,
  al_cambiar,
}: {
  clave: string;
  valor: string;
  cargando: boolean;
  al_cambiar: (valor: string) => void;
}) {
  const definicion = _DEFINICIONES.get(clave);
  const numerico = clave !== "FERIADOS";
  return (
    <CampoTexto
      etiqueta={definicion ? `${definicion.etiqueta} (${definicion.unidad})` : clave}
      type={numerico ? "number" : "text"}
      min={numerico ? "1" : undefined}
      value={valor}
      disabled={cargando}
      onChange={(evento) => al_cambiar(evento.target.value)}
    />
  );
}

function TarjetaGrupo({
  grupo,
  valores,
  cargando,
}: {
  grupo: Grupo;
  valores: Map<string, string>;
  cargando: boolean;
}) {
  const cliente_consultas = useQueryClient();
  const [editados, set_editados] = useState<Record<string, string>>({});
  const cambios = Object.fromEntries(
    Object.entries(editados).filter(([clave, valor]) => valor !== (valores.get(clave) ?? "")),
  );
  const mutacion = useMutation({
    mutationFn: () => actualizar_parametros_sistema(cambios),
    onSuccess: (vigentes) => {
      cliente_consultas.setQueryData(_CLAVE_CONSULTA, vigentes);
      set_editados({});
    },
  });

  // El aviso dura hasta que el usuario vuelve a editar.
  const guardado = mutacion.isSuccess && Object.keys(cambios).length === 0;
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>{grupo.titulo}</div>
      <div className={estilos.campos_parametros}>
        {grupo.claves.map((clave) => (
          <CampoParametro
            key={clave}
            clave={clave}
            valor={editados[clave] ?? valores.get(clave) ?? ""}
            cargando={cargando}
            al_cambiar={(valor) => set_editados({ ...editados, [clave]: valor })}
          />
        ))}
      </div>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudieron guardar." />
      {guardado ? <Mensaje tipo="exito" texto="Cambios guardados." /> : null}
      <div className={estilos.acciones_parametros}>
        <Boton
          variante="primario"
          onClick={() => mutacion.mutate()}
          disabled={Object.keys(cambios).length === 0 || mutacion.isPending}
        >
          Guardar
        </Boton>
      </div>
    </div>
  );
}

export function AdministracionParametros() {
  const consulta = useQuery({ queryKey: _CLAVE_CONSULTA, queryFn: listar_parametros_sistema });
  const valores = new Map((consulta.data ?? []).map((p) => [p.clave, p.valor]));

  return (
    <div>
      <TituloPagina titulo="Parámetros del sistema" />
      <MensajeErrorMutacion
        error={consulta.error}
        texto_por_defecto="No se pudieron cargar los parámetros."
      />
      <div className={estilos.rejilla_parametros}>
        {_GRUPOS.map((grupo) => (
          <TarjetaGrupo
            key={grupo.titulo}
            grupo={grupo}
            valores={valores}
            cargando={consulta.isPending}
          />
        ))}
      </div>
      <OpcionNavegacionRobot />
    </div>
  );
}
