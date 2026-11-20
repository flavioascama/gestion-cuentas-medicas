import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { obtener_solicitud_atencion } from "../../api/acreditacion";
import { ErrorApi } from "../../api/cliente_http";
import { ultima_consulta_cobertura, type UltimaConsultaCobertura } from "../../api/contingencia";
import { solicitar_verificacion_cobertura, type AcreditacionRespuesta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import { AccionCoberturaContingencia } from "../contingencia/accion_cobertura_contingencia";
import {
  AFILIACIONES,
  DOCUMENTOS_AUTORIZACION,
  nombre_en_catalogo,
} from "../contingencia/catalogos_cobertura";
import { SesionPlataforma } from "../plataformas/sesion_plataforma";
import { usar_acreditacion_cuenta } from "./usar_cuentas";
import estilos from "./detalle_cuenta.module.css";
import propios from "./seccion_acreditacion.module.css";

// Acreditacion del asegurado. En el TO-BE de la tesis la cuenta se registra
// en la admision (actividad 1) y enseguida se acredita al asegurado en
// ACREDITA SALUD (actividad 2). Desde el 2026-11-18 es un paso de la linea
// de la cuenta, con un solo boton: la sesion con ACREDITA SALUD se maneja
// sola y la persona solo responde el codigo de verificacion cuando hace
// falta. Muestra como termino la ultima consulta en lenguaje de la clinica
// (nunca el texto interno del robot).

const _URL_PORTAL =
  (import.meta.env.VITE_URL_PORTAL_ACREDITA_SALUD as string | undefined) ?? "http://localhost:8100";
const _RUTA_CONSULTA = "/acreditacion/iafas";
const _EN_CURSO = new Set(["EN_CURSO", "REQUIERE_SESION"]);

function texto_copago(a: AcreditacionRespuesta): string {
  if (a.tipo_copago === "coaseguro") return `Coaseguro ${a.porcentaje_coaseguro ?? 0} %`;
  if (a.tipo_copago === "fijo") return `Monto fijo ${formatear_monto(a.monto_copago_fijo ?? 0)}`;
  return "—";
}

function datos_acreditacion(acreditacion: AcreditacionRespuesta) {
  const manual = acreditacion.componente_ejecutor === "registro_manual_contingencia";
  return [
    { etiqueta: "Condición de cobertura", valor: acreditacion.condicion_cobertura },
    {
      etiqueta: "Tipo de afiliación",
      valor: nombre_en_catalogo(AFILIACIONES, acreditacion.tipo_afiliacion),
    },
    { etiqueta: "Código de asegurado", valor: acreditacion.codigo_asegurado },
    { etiqueta: "Código de acreditación", valor: acreditacion.codigo_autorizacion },
    {
      etiqueta: "Tipo de documento de autorización",
      valor: nombre_en_catalogo(DOCUMENTOS_AUTORIZACION, acreditacion.tipo_documento_autorizacion),
    },
    { etiqueta: "Plan", valor: acreditacion.plan ?? "—" },
    { etiqueta: "Copago", valor: texto_copago(acreditacion) },
    {
      etiqueta: "Preexistencias o restricciones",
      valor: acreditacion.preexistencias.length > 0 ? acreditacion.preexistencias.join(", ") : "—",
    },
    { etiqueta: "Acreditado el", valor: formatear_fecha_hora(acreditacion.instante) },
    {
      etiqueta: "Vigente desde",
      valor: acreditacion.vigente_desde ? formatear_fecha(acreditacion.vigente_desde) : "—",
    },
    {
      etiqueta: "Vigente hasta",
      valor: acreditacion.vigente_hasta ? formatear_fecha(acreditacion.vigente_hasta) : "—",
    },
    {
      etiqueta: "Origen",
      valor: manual ? "Registrada en modo de contingencia" : "Obtenida de ACREDITA SALUD",
    },
  ];
}

function ResultadoAcreditacion({
  acreditacion,
  cuenta_id,
}: {
  acreditacion: AcreditacionRespuesta;
  cuenta_id: number;
}) {
  const datos = datos_acreditacion(acreditacion);
  return (
    <>
      <div className={estilos.datos_en_linea}>
        {datos.map((dato) => (
          <div key={dato.etiqueta} className={estilos.campo_dato}>
            <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
            <span className={estilos.valor_dato}>{dato.valor}</span>
          </div>
        ))}
      </div>
      {acreditacion.tiene_solicitud_atencion ? (
        <VerSolicitudAtencion cuenta_id={cuenta_id} />
      ) : null}
    </>
  );
}

function VerSolicitudAtencion({ cuenta_id }: { cuenta_id: number }) {
  const mutacion = useMutation({
    mutationFn: async () => {
      const url = URL.createObjectURL(await obtener_solicitud_atencion(cuenta_id));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
  });
  return (
    <>
      <div className={estilos.fila_accion}>
        <Boton
          variante="secundario"
          onClick={() => mutacion.mutate()}
          disabled={mutacion.isPending}
        >
          Ver solicitud de atención
        </Boton>
      </div>
      {mutacion.isError ? (
        <Mensaje
          tipo="error"
          texto={mutacion.error instanceof ErrorApi ? mutacion.error.message : "No se pudo abrir."}
        />
      ) : null}
    </>
  );
}

function EstadoUltimaConsulta({ ultima }: { ultima: UltimaConsultaCobertura | null | undefined }) {
  if (!ultima) return null;
  if (_EN_CURSO.has(ultima.resultado)) {
    return <p className={propios.estado}>Consultando la acreditación…</p>;
  }
  if (ultima.resultado === "SIN_RESPUESTA") {
    return (
      <Mensaje
        tipo="advertencia"
        texto={`ACREDITA SALUD no respondió tras ${ultima.intentos} intentos.`}
      />
    );
  }
  if (ultima.resultado !== "SIN_RESULTADO") return null;
  return (
    <div className={propios.no_encontrado} role="status">
      <p className={propios.no_encontrado_titulo}>
        {ultima.mensaje ?? "ACREDITA SALUD no encontró al asegurado."}
      </p>
      <a
        className={propios.enlace_portal}
        href={`${_URL_PORTAL}${_RUTA_CONSULTA}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Abrir ACREDITA SALUD ↗
      </a>
    </div>
  );
}

function usar_ultima_consulta(cuenta_id: number) {
  const cliente_consultas = useQueryClient();
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "ultima_consulta_cobertura"],
    queryFn: () => ultima_consulta_cobertura(cuenta_id),
    refetchInterval: (query) => (_EN_CURSO.has(query.state.data?.resultado ?? "") ? 2000 : false),
  });
  // Solo cuando una consulta termina mientras se la esta viendo (pasa de
  // en curso a terminada) se refrescan la acreditacion, la completitud y
  // la contingencia; al abrir la pagina con una consulta ya terminada no
  // hay nada que refrescar.
  const resultado = consulta.data?.resultado;
  const anterior = useRef(resultado);
  useEffect(() => {
    const venia_en_curso = _EN_CURSO.has(anterior.current ?? "");
    anterior.current = resultado;
    if (!venia_en_curso || !resultado || _EN_CURSO.has(resultado)) return;
    for (const clave of ["acreditacion", "completitud", "contingencia_cobertura"]) {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id, clave] });
    }
  }, [resultado, cuenta_id, cliente_consultas]);
  return consulta;
}

function PendienteAcreditacion({ cuenta_id }: { cuenta_id: number }) {
  const cliente_consultas = useQueryClient();
  const consulta = usar_ultima_consulta(cuenta_id);
  const en_curso = _EN_CURSO.has(consulta.data?.resultado ?? "");
  const mutacion = useMutation({
    mutationFn: () => solicitar_verificacion_cobertura(cuenta_id),
    onSuccess: () =>
      void cliente_consultas.invalidateQueries({
        queryKey: ["cuentas", cuenta_id, "ultima_consulta_cobertura"],
      }),
  });
  return (
    <>
      <div className={estilos.fila_accion}>
        <Boton
          variante="primario"
          onClick={() => mutacion.mutate()}
          disabled={mutacion.isPending || en_curso}
        >
          Consultar acreditación
        </Boton>
      </div>
      {mutacion.isError ? (
        <Mensaje
          tipo="error"
          texto={
            mutacion.error instanceof ErrorApi ? mutacion.error.message : "No se pudo consultar."
          }
        />
      ) : null}
      <EstadoUltimaConsulta ultima={consulta.data} />
      {/* La sesion se pide solo cuando el robot dice que la necesita: pedirla
          antes dejaria al robot esperando un codigo que quiza no hacia falta. */}
      <SesionPlataforma
        plataforma="acredita_salud"
        nombre="ACREDITA SALUD"
        necesita={consulta.data?.resultado === "REQUIERE_SESION"}
      />
      <AccionCoberturaContingencia cuenta_id={cuenta_id} />
    </>
  );
}

export function ContenidoAcreditacion({ cuenta_id }: { cuenta_id: number }) {
  const { sesion } = usar_sesion();
  const consulta_acreditacion = usar_acreditacion_cuenta(cuenta_id);
  const es_analista = sesion?.roles.includes("analista") ?? false;
  if (consulta_acreditacion.isLoading) return null;
  const acreditacion = consulta_acreditacion.data;
  if (acreditacion) {
    // Mientras la cuenta siga registrada y sin comprobante, se puede volver
    // a consultar: la respuesta nueva pasa a ser la vigente.
    return (
      <>
        <ResultadoAcreditacion acreditacion={acreditacion} cuenta_id={cuenta_id} />
        {es_analista && acreditacion.admite_reconsulta ? (
          <PendienteAcreditacion cuenta_id={cuenta_id} />
        ) : null}
      </>
    );
  }
  return es_analista ? <PendienteAcreditacion cuenta_id={cuenta_id} /> : null;
}
