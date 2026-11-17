import { useQuery } from "@tanstack/react-query";
import { listar_parametros_sistema } from "../../api/parametros";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha } from "../../utilidades/formato";
import { con_unidad } from "./formato_administracion";
import { OpcionNavegacionRobot } from "./opcion_navegacion_robot";
import estilos from "./administracion.module.css";

// Parametros del sistema (fijados en el despliegue), con nombres y unidades
// legibles agrupados por tema, en vez de las claves de configuracion
// (rediseno de la administracion, 2026-11-15).
interface DefinicionParametro {
  etiqueta: string;
  formatear: (valor: string) => string;
}

interface FilaParametro {
  clave: string;
  etiqueta: string;
  valor: string;
}

function feriados(valor: string): string {
  const fechas = valor
    .split(",")
    .map((fecha) => fecha.trim())
    .filter((fecha) => /^\d{4}-\d{2}-\d{2}$/.test(fecha));
  return fechas.length > 0 ? fechas.map(formatear_fecha).join(", ") : "Sin feriados registrados";
}

const _DEFINICIONES = new Map<string, DefinicionParametro>([
  [
    "DURACION_SESION_MINUTOS",
    { etiqueta: "Duración de la sesión", formatear: (v) => con_unidad(v, "minuto", "minutos") },
  ],
  [
    "MAXIMO_INTENTOS_FALLIDOS_SESION",
    {
      etiqueta: "Intentos fallidos antes del bloqueo",
      formatear: (v) => con_unidad(v, "intento", "intentos"),
    },
  ],
  [
    "DURACION_BLOQUEO_SESION_MINUTOS",
    { etiqueta: "Duración del bloqueo", formatear: (v) => con_unidad(v, "minuto", "minutos") },
  ],
  [
    "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO",
    {
      etiqueta: "Plazo para reenviar un lote rechazado",
      formatear: (v) => con_unidad(v, "día", "días"),
    },
  ],
  [
    "DIAS_AVISO_PREVIO_VENCIMIENTO",
    {
      etiqueta: "Aviso antes del vencimiento de un plazo",
      formatear: (v) => con_unidad(v, "día", "días"),
    },
  ],
  [
    "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA",
    {
      etiqueta: "Aviso antes del fin de vigencia de la carta de garantía",
      formatear: (v) => con_unidad(v, "día", "días"),
    },
  ],
  [
    "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS",
    {
      etiqueta: "Revisión de vencimientos",
      formatear: (v) => `Cada ${con_unidad(v, "minuto", "minutos")}`,
    },
  ],
  [
    "TEMPORIZADOR_INTERVALO_CADENA_HORAS",
    {
      etiqueta: "Verificación de la integridad del historial",
      formatear: (v) => `Cada ${con_unidad(v, "hora", "horas")}`,
    },
  ],
  ["FERIADOS", { etiqueta: "Feriados", formatear: feriados }],
]);

const _GRUPOS: { titulo: string; claves: string[] }[] = [
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

const _COLUMNAS: ColumnaTabla<FilaParametro>[] = [
  { clave: "etiqueta", encabezado: "Parámetro" },
  { clave: "valor", encabezado: "Valor" },
];

function filas_del_grupo(claves: string[], valores: Map<string, string>): FilaParametro[] {
  return claves
    .filter((clave) => valores.has(clave))
    .map((clave) => {
      const definicion = _DEFINICIONES.get(clave);
      const valor = valores.get(clave) ?? "";
      return {
        clave,
        etiqueta: definicion?.etiqueta ?? clave,
        valor: definicion ? definicion.formatear(valor) : valor,
      };
    });
}

export function AdministracionParametros() {
  const consulta = useQuery({
    queryKey: ["administracion", "parametros", "sistema"],
    queryFn: listar_parametros_sistema,
  });
  const valores = new Map((consulta.data ?? []).map((p) => [p.clave, p.valor]));

  return (
    <div>
      <TituloPagina titulo="Parámetros del sistema" />
      {_GRUPOS.map((grupo) => (
        <div key={grupo.titulo} className={estilos.seccion}>
          <div className={estilos.titulo_seccion}>{grupo.titulo}</div>
          <div className={estilos.tabla_parametros}>
            <TablaDatos
              columnas={_COLUMNAS}
              filas={filas_del_grupo(grupo.claves, valores)}
              obtener_clave={(fila) => fila.clave}
              cargando={consulta.isPending}
              error={consulta.error}
              mensaje_vacio="Sin datos."
            />
          </div>
        </div>
      ))}
      <OpcionNavegacionRobot />
    </div>
  );
}
