import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ProcedimientoPorCodificar } from "../../api/atenciones";
import { obtener_carta_garantia } from "../../api/carta_garantia";
import { consultar_documentos_pago } from "../../api/comprobante";
import type { RespuestaCompletitudCuenta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_puede_codificar } from "./codificacion_cuenta";
import { ListaPorCodificar } from "./por_codificar_cuenta";
import { texto_faltan_por_codificar, usar_por_codificar } from "./usar_por_codificar";
import { RegistrarDiagnostico } from "./registrar_diagnostico";
import { ContenidoAcreditacion } from "./seccion_acreditacion";
import { ContenidoCartaGarantia } from "./seccion_carta_garantia";
import { ContenidoComprobante } from "./seccion_comprobante";
import {
  usar_acreditacion_cuenta,
  usar_completitud_cuenta,
  usar_en_correccion_validador,
} from "./usar_cuentas";
import estilos_seccion from "./detalle_cuenta.module.css";
import estilos from "./linea_pasos_cuenta.module.css";

// Linea de pasos de la cuenta, en el orden en que ocurren (2026-11-18):
// registro, acreditacion, carta de garantia (opcional, va antes de la
// atencion), diagnostico y procedimientos, comprobante de pago y lote. Cada
// paso dice si ya se hizo y, al elegirlo, muestra debajo lo que permite
// completarlo. El estado sale de la completitud que calcula el backend.

type Clave = "registro" | "acreditacion" | "carta" | "clinica" | "comprobante" | "lote";

interface Paso {
  clave: Clave;
  titulo: string;
  hecho: boolean;
  estado: string;
  // Quien mira tiene algo que ver o hacer en este paso.
  con_panel: boolean;
  // Un paso que puede quedar sin hacerse (la carta fuera de hospitalizacion).
  opcional?: boolean;
}

// Lo que cada panel necesita saber de la cuenta y de quien mira.
interface Situacion {
  analista: boolean;
  // Ve el resultado de la acreditacion (analista, auditor y jefe).
  ve_acreditacion: boolean;
  codifica: boolean;
  // Quien puede registrar o cambiar el diagnostico segun el estado (igual que el servidor).
  diagnostica: boolean;
  registra_carta: boolean;
  ve_lotes: boolean;
  acreditada: boolean;
  // La aseguradora respondio que no cubre al asegurado.
  no_acreditable: boolean;
  con_diagnostico: boolean;
  codificada: boolean;
  facturada: boolean;
  // El servidor dice que el comprobante vigente ya no refleja la cuenta.
  comprobante_desfasado: boolean;
  tiene_carta: boolean;
  // En hospitalizacion la carta de garantia es obligatoria.
  carta_obligatoria: boolean;
  por_codificar: ProcedimientoPorCodificar[];
  lote: RespuestaCompletitudCuenta["lote"];
  estado_cuenta: string;
}

// Misma regla que el backend (dominio/acreditacion/carta_garantia.py).
const _ESTADOS_CARTA = new Set(["REGISTRADA", "RECHAZADA"]);
// Misma regla que el backend (dominio/integracion/diagnostico_cuenta.py).
const _ESTADOS_CON_DIAGNOSTICO_EDITABLE = new Set(["REGISTRADA", "RECHAZADA"]);

function texto_estado(hecho: boolean, pendiente = "Pendiente"): string {
  return hecho ? "Hecho" : pendiente;
}

function estado_clinico(s: Situacion): string {
  if (!s.con_diagnostico) return "Falta el diagnóstico";
  if (s.por_codificar.length > 0) return texto_faltan_por_codificar(s.por_codificar.length);
  return s.codifica ? "Faltan procedimientos" : "Pendiente del auditor médico";
}

// Lo que falta antes de emitir el comprobante: va al final.
function faltantes_comprobante(s: Situacion): string[] {
  const faltantes: string[] = [];
  if (!s.acreditada) faltantes.push("la acreditación");
  if (!s.con_diagnostico) faltantes.push("el diagnóstico");
  if (s.por_codificar.length > 0) faltantes.push("los procedimientos por codificar");
  else if (!s.codificada) faltantes.push("al menos un procedimiento");
  if (s.carta_obligatoria && !s.tiene_carta) faltantes.push("la carta de garantía");
  return faltantes;
}

function paso_clinico(s: Situacion): Paso {
  const hecho = s.con_diagnostico && s.codificada && s.por_codificar.length === 0;
  return {
    clave: "clinica",
    titulo: "Diagnóstico y procedimientos",
    hecho,
    estado: hecho ? "Hecho" : estado_clinico(s),
    con_panel: s.diagnostica || s.codifica || s.por_codificar.length > 0,
  };
}

function paso_lote(s: Situacion): Paso {
  const en_lote = Boolean(s.lote);
  return {
    clave: "lote",
    titulo: "Lote",
    hecho: en_lote,
    estado: s.lote ? `N.° ${s.lote.numero}` : "Pendiente",
    con_panel: (en_lote && s.ve_lotes) || (s.analista && s.estado_cuenta === "FACTURADA"),
  };
}

function paso_comprobante(s: Situacion): Paso {
  const desfasado = s.facturada && s.comprobante_desfasado;
  return {
    clave: "comprobante",
    titulo: "Comprobante de pago",
    hecho: s.facturada && !desfasado,
    estado: desfasado ? "No refleja la cuenta" : texto_estado(s.facturada),
    con_panel: s.analista || s.facturada,
  };
}

function estado_carta(s: Situacion): string {
  if (s.tiene_carta) return "Registrada";
  return s.carta_obligatoria ? "Falta la carta de garantía" : "Opcional";
}

function armar_pasos(s: Situacion): Paso[] {
  return [
    { clave: "registro", titulo: "Registro", hecho: true, estado: "Hecho", con_panel: false },
    {
      clave: "acreditacion",
      titulo: "Acreditación",
      hecho: s.acreditada,
      estado: texto_estado(s.acreditada, s.no_acreditable ? "No acreditable" : "Pendiente"),
      con_panel: s.analista || (s.ve_acreditacion && s.acreditada),
    },
    {
      clave: "carta",
      titulo: "Carta de garantía",
      hecho: s.tiene_carta,
      estado: estado_carta(s),
      con_panel: s.tiene_carta || s.registra_carta,
      opcional: !s.carta_obligatoria,
    },
    paso_clinico(s),
    paso_comprobante(s),
    paso_lote(s),
  ];
}

function diagnostico_editable(
  estado: string,
  con_diagnostico: boolean,
  en_correccion: boolean,
): boolean {
  if (en_correccion || _ESTADOS_CON_DIAGNOSTICO_EDITABLE.has(estado)) return true;
  return estado === "FACTURADA" && !con_diagnostico;
}

function usar_permisos(cuenta_id: number, estado: string, con_diagnostico: boolean) {
  const { sesion } = usar_sesion();
  const en_correccion = usar_en_correccion_validador(cuenta_id);
  const codifica = usar_puede_codificar(estado, cuenta_id);
  const roles = sesion?.roles ?? [];
  const analista = roles.includes("analista");
  const con_rol = analista || roles.includes("auditor");
  const editable = diagnostico_editable(estado, con_diagnostico, en_correccion);
  return {
    analista,
    ve_acreditacion: con_rol || roles.includes("jefe"),
    codifica,
    diagnostica: editable && con_rol,
    registra_carta: analista && _ESTADOS_CARTA.has(estado),
    ve_lotes: analista || roles.includes("jefe"),
  };
}

function usar_comprobante_desfasado(cuenta_id: number, facturada: boolean): boolean {
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comprobante"],
    queryFn: () => consultar_documentos_pago(cuenta_id),
    enabled: facturada,
  });
  return Boolean(consulta.data?.desfasado);
}

function usar_situacion(cuenta_id: number, estado: string): Situacion | null {
  const cliente_consultas = useQueryClient();
  const completitud = usar_completitud_cuenta(cuenta_id);
  const carta = useQuery({
    queryKey: ["cuentas", cuenta_id, "carta-garantia"],
    queryFn: () => obtener_carta_garantia(cuenta_id),
  });
  const por_codificar = usar_por_codificar(cuenta_id);
  const acreditacion = usar_acreditacion_cuenta(cuenta_id);
  const piezas = completitud.data?.piezas ?? [];
  const hecha = (clave: string) => piezas.some((pieza) => pieza.clave === clave && pieza.completa);
  const con_diagnostico = hecha("diagnostico");
  const permisos = usar_permisos(cuenta_id, estado, con_diagnostico);
  const estado_cuenta = completitud.data?.estado_cuenta;
  const desfasado = usar_comprobante_desfasado(cuenta_id, hecha("comprobante"));

  // Si el estado cambia (la cuenta queda Facturada al emitir el comprobante),
  // la insignia de estado del encabezado (otra consulta) se refresca tambien.
  useEffect(() => {
    if (estado_cuenta) {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id], exact: true });
    }
  }, [estado_cuenta, cuenta_id, cliente_consultas]);

  if (!completitud.data || carta.isPending || por_codificar.cargando) return null;
  // La cobertura queda incompleta solo por la carta: el asegurado ya esta acreditado.
  const carta_obligatoria = piezas.some(
    (pieza) => pieza.clave === "cobertura" && pieza.accion === "registrar_carta_garantia",
  );
  return {
    ...permisos,
    acreditada: hecha("cobertura") || carta_obligatoria,
    // Misma regla que el servidor (dominio/acreditacion/valores.py, es_acreditable).
    no_acreditable: Boolean(
      acreditacion.data?.condicion_cobertura.trim().toUpperCase().startsWith("NO ACREDITABLE"),
    ),
    con_diagnostico,
    codificada: hecha("codificacion"),
    facturada: hecha("comprobante"),
    comprobante_desfasado: desfasado,
    tiene_carta: Boolean(carta.data),
    carta_obligatoria,
    por_codificar: por_codificar.pendientes,
    lote: completitud.data.lote ?? null,
    estado_cuenta: completitud.data.estado_cuenta,
  };
}

function PasoLinea({
  paso,
  numero,
  abierto,
  al_elegir,
}: {
  paso: Paso;
  numero: number;
  abierto: boolean;
  al_elegir: () => void;
}) {
  const contenido = (
    <>
      <span
        className={`${estilos.marca} ${paso.hecho ? estilos.marca_hecha : ""}`}
        aria-hidden="true"
      >
        {paso.hecho ? "✓" : numero}
      </span>
      <span className={estilos.titulo}>{paso.titulo}</span>
      <span className={estilos.estado}>{paso.estado}</span>
    </>
  );
  const clases = [
    estilos.paso,
    paso.hecho ? estilos.paso_hecho : "",
    abierto ? estilos.abierto : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <li className={clases}>
      {paso.con_panel ? (
        <button
          type="button"
          className={estilos.boton_paso}
          aria-expanded={abierto}
          onClick={al_elegir}
        >
          {contenido}
        </button>
      ) : (
        <div className={estilos.boton_paso}>{contenido}</div>
      )}
    </li>
  );
}

interface PropiedadesLinea {
  cuenta_id: number;
  estado: string;
  al_codificar: () => void;
  al_codificar_pendiente: (pendiente: ProcedimientoPorCodificar) => void;
}

function PanelClinico({
  cuenta_id,
  situacion,
  al_codificar,
  al_codificar_pendiente,
}: PropiedadesLinea & { situacion: Situacion }) {
  return (
    <>
      {situacion.diagnostica ? <RegistrarDiagnostico cuenta_id={cuenta_id} /> : null}
      {situacion.codifica ? (
        <div className={estilos_seccion.fila_accion}>
          <Boton variante="primario" onClick={al_codificar}>
            Agregar procedimiento
          </Boton>
        </div>
      ) : null}
      {situacion.por_codificar.length > 0 ? (
        <ListaPorCodificar
          pendientes={situacion.por_codificar}
          al_codificar={situacion.codifica ? al_codificar_pendiente : null}
        />
      ) : null}
    </>
  );
}

function PanelLote({ situacion }: { situacion: Situacion }) {
  if (situacion.lote) {
    return <Link to={`/lotes/${situacion.lote.lote_id}`}>Ver el lote {situacion.lote.numero}</Link>;
  }
  return <Link to="/lotes">Ir a Lotes para generarlo</Link>;
}

function PanelPaso({
  clave,
  situacion,
  ...linea
}: PropiedadesLinea & { clave: Clave; situacion: Situacion }) {
  const { cuenta_id, estado } = linea;
  if (clave === "acreditacion") return <ContenidoAcreditacion cuenta_id={cuenta_id} />;
  if (clave === "carta") return <ContenidoCartaGarantia cuenta_id={cuenta_id} estado={estado} />;
  if (clave === "clinica") {
    return <PanelClinico situacion={situacion} {...linea} />;
  }
  if (clave === "comprobante") {
    return (
      <ContenidoComprobante
        cuenta_id={cuenta_id}
        estado={estado}
        faltantes={faltantes_comprobante(situacion)}
      />
    );
  }
  return clave === "lote" ? <PanelLote situacion={situacion} /> : null;
}

// Al abrir la cuenta queda elegido el primer paso pendiente en el que quien
// mira puede hacer algo; la carta de garantia es opcional y no cuenta.
function paso_inicial(pasos: Paso[]): Clave | null {
  const pendiente = pasos.find((paso) => !paso.hecho && paso.con_panel && !paso.opcional);
  return pendiente?.clave ?? null;
}

function LineaPasos({ situacion, ...linea }: PropiedadesLinea & { situacion: Situacion }) {
  const pasos = armar_pasos(situacion);
  const [abierto, set_abierto] = useState<Clave | null>(() => paso_inicial(pasos));
  return (
    <div className={estilos_seccion.seccion}>
      <ol className={estilos.linea} aria-label="Pasos de la cuenta">
        {pasos.map((paso, indice) => (
          <PasoLinea
            key={paso.clave}
            paso={paso}
            numero={indice + 1}
            abierto={abierto === paso.clave}
            al_elegir={() => set_abierto(abierto === paso.clave ? null : paso.clave)}
          />
        ))}
      </ol>
      {abierto ? (
        <div className={estilos.panel}>
          <PanelPaso clave={abierto} situacion={situacion} {...linea} />
        </div>
      ) : null}
    </div>
  );
}

export function LineaPasosCuenta(linea: PropiedadesLinea) {
  const situacion = usar_situacion(linea.cuenta_id, linea.estado);
  if (!situacion) return null;
  return <LineaPasos situacion={situacion} {...linea} />;
}
