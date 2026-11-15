import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { ErrorApi } from "../../api/cliente_http";
import { ultima_consulta_cobertura, type UltimaConsultaCobertura } from "../../api/contingencia";
import { solicitar_verificacion_cobertura, type AcreditacionRespuesta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { GestorSesionPlataforma } from "../../componentes_base/gestor_sesion_plataforma";
import { Mensaje } from "../../componentes_base/mensaje";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_fecha_hora } from "../../utilidades/formato";
import { AccionCoberturaContingencia } from "../contingencia/accion_cobertura_contingencia";
import { usar_acreditacion_cuenta } from "./usar_cuentas";
import estilos from "./detalle_cuenta.module.css";
import propios from "./seccion_acreditacion.module.css";

// "Acreditacion del asegurado" (rediseno del 2026-11-12, pedido del
// usuario). En el TO-BE de la tesis la cuenta se registra en la admision
// (actividad 1) y enseguida se acredita al asegurado en ACREDITA SALUD
// (actividad 2): no es un tramite posterior a la atencion, es la pieza de
// la admision que la facturacion necesita. La seccion lo dice asi, muestra
// como termino la ultima consulta en lenguaje de la clinica (nunca el
// texto interno del robot) y, si el portal no encontro al asegurado, lleva
// al mismo portal para consultarlo a mano.

const _URL_PORTAL =
  (import.meta.env.VITE_URL_PORTAL_ACREDITA_SALUD as string | undefined) ?? "http://localhost:8100";
const _RUTA_CONSULTA = "/acreditacion/iafas";
const _EN_CURSO = new Set(["EN_CURSO", "REQUIERE_SESION"]);

function ResultadoAcreditacion({ acreditacion }: { acreditacion: AcreditacionRespuesta }) {
  const manual = acreditacion.componente_ejecutor === "registro_manual_contingencia";
  const datos = [
    { etiqueta: "Condición de cobertura", valor: acreditacion.condicion_cobertura },
    { etiqueta: "Código de acreditación", valor: acreditacion.codigo_autorizacion },
    { etiqueta: "Acreditado el", valor: formatear_fecha_hora(acreditacion.instante) },
    {
      etiqueta: "Vigente hasta",
      valor: acreditacion.vigente_hasta ? formatear_fecha(acreditacion.vigente_hasta) : "—",
    },
  ];
  return (
    <div className={estilos.lista_compacta}>
      {datos.map((dato) => (
        <div key={dato.etiqueta} className={estilos.campo_dato}>
          <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
          <span className={estilos.valor_dato}>{dato.valor}</span>
        </div>
      ))}
      <span className={propios.origen}>
        {manual ? "Registrada en modo de contingencia." : "Obtenida de ACREDITA SALUD."}
      </span>
    </div>
  );
}

function EstadoUltimaConsulta({ ultima }: { ultima: UltimaConsultaCobertura | null | undefined }) {
  if (!ultima) return null;
  if (ultima.resultado === "EN_CURSO") {
    return (
      <p className={propios.estado}>Consultando ACREDITA SALUD… (intento {ultima.intentos + 1})</p>
    );
  }
  if (ultima.resultado === "REQUIERE_SESION") {
    return <Mensaje tipo="advertencia" texto="Esperando sesión en ACREDITA SALUD." />;
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
          Consultar en ACREDITA SALUD
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
      <AccionCoberturaContingencia cuenta_id={cuenta_id} />
      <GestorSesionPlataforma plataforma="acredita_salud" nombre_visible="ACREDITA SALUD" />
    </>
  );
}

export function SeccionAcreditacion({ cuenta_id }: { cuenta_id: number }) {
  const { sesion } = usar_sesion();
  const consulta_acreditacion = usar_acreditacion_cuenta(cuenta_id);
  if (!sesion?.roles.includes("analista")) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Acreditación del asegurado</div>
      {consulta_acreditacion.data ? (
        <ResultadoAcreditacion acreditacion={consulta_acreditacion.data} />
      ) : consulta_acreditacion.isLoading ? null : (
        <PendienteAcreditacion cuenta_id={cuenta_id} />
      )}
    </div>
  );
}
