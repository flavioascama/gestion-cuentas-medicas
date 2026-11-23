import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { consultar_documentos_pago } from "../../api/comprobante";
import {
  conciliar_pago,
  corregir_liquidacion,
  registrar_liquidacion,
  type Liquidacion,
} from "../../api/liquidacion";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { RegistroManual } from "../../componentes_base/registro_manual";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { usar_filas_copago, type FilaMonto } from "./usar_filas_copago";
import { corregir_pago, usar_liquidacion_cuenta } from "./usar_liquidacion";

// Lo facturado a la IAFAS, como referencia de lo que liquida y paga
// (2026-11-18): es el total del comprobante vigente, menos su nota de
// crédito o más su nota de débito.
// La nota se registra sin IGV: se lleva a la base del comprobante.
function neto_con_nota(
  total: string,
  valor_venta: string | null | undefined,
  igv: string | null | undefined,
  nota: { tipo: string; monto: string },
): string {
  const venta = Number(valor_venta ?? 0);
  const tasa = venta > 0 ? Number(igv ?? 0) / venta : 0;
  const signo = nota.tipo === "C" ? -1 : 1;
  return (Number(total) + signo * Number(nota.monto) * (1 + tasa)).toFixed(2);
}

function usar_total_facturado(cuenta_id: number): string | null {
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comprobante"],
    queryFn: () => consultar_documentos_pago(cuenta_id),
  });
  const vigente = consulta.data?.vigente;
  const nota = consulta.data?.nota;
  if (!vigente?.total || !nota) return vigente?.total ?? null;
  return neto_con_nota(vigente.total, vigente.valor_venta, vigente.igv, nota);
}

// Lo facturado que la IAFAS no liquido (tercera auditoria, medio 2): la
// fila solo aparece si lo liquidado es menor que el total facturado.
function filas_no_reconocido(facturado: string | null, liquidado: string | undefined): FilaMonto[] {
  if (facturado == null || !liquidado) return [];
  const centimos = Math.round(Number(facturado) * 100) - Math.round(Number(liquidado) * 100);
  if (centimos <= 0) return [];
  return [{ etiqueta: "No reconocido por la IAFAS", valor: formatear_monto(centimos / 100) }];
}

// Diferencia = pagado - liquidado: negativa, falta cobrar; positiva, se pago de mas.
function texto_diferencia(diferencia: string | null | undefined): string {
  if (!diferencia) return "—";
  const valor = Number(diferencia);
  if (valor === 0) return formatear_monto(valor);
  return `${formatear_monto(Math.abs(valor))} ${valor < 0 ? "por cobrar" : "pagado de más"}`;
}

function DatosLiquidacion({
  facturado,
  copago,
  liquidacion,
}: {
  facturado: string | null;
  copago: FilaMonto[];
  liquidacion: Liquidacion | null;
}) {
  const monto = (valor: string | null | undefined) => (valor ? formatear_monto(valor) : "—");
  const conciliado_en = liquidacion?.conciliado_en;
  const datos: FilaMonto[] = [
    { etiqueta: "Total facturado", valor: monto(facturado) },
    ...copago,
    { etiqueta: "Liquidado por la IAFAS", valor: monto(liquidacion?.monto_liquidado) },
    ...filas_no_reconocido(facturado, liquidacion?.monto_liquidado),
    { etiqueta: "Pagado por la IAFAS", valor: monto(liquidacion?.monto_pagado) },
    { etiqueta: "Diferencia", valor: texto_diferencia(liquidacion?.diferencia) },
    { etiqueta: "Conciliado", valor: conciliado_en ? formatear_fecha_hora(conciliado_en) : "—" },
  ];
  return (
    <div className={estilos.rejilla}>
      {datos.map((dato) => (
        <div key={dato.etiqueta} className={estilos.campo_dato}>
          <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
          <span className={estilos.valor_dato}>{dato.valor}</span>
        </div>
      ))}
    </div>
  );
}

function FormularioRegistrarLiquidacion({
  cuenta_id,
  liquidacion = null,
  al_corregir,
}: {
  cuenta_id: number;
  // Con la liquidacion ya registrada, el formulario la corrige.
  liquidacion?: Liquidacion | null;
  al_corregir?: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [monto_liquidado, set_monto_liquidado] = useState(
    liquidacion ? String(liquidacion.monto_liquidado) : "",
  );

  const mutacion = useMutation({
    mutationFn: async () => {
      if (liquidacion) await corregir_liquidacion(cuenta_id, monto_liquidado);
      else await registrar_liquidacion(cuenta_id, monto_liquidado);
    },
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      if (liquidacion) al_corregir?.();
      else set_monto_liquidado("");
    },
  });

  return (
    <div className={estilos.fila_accion}>
      <CampoTexto
        etiqueta="Monto que liquidó la IAFAS"
        obligatorio
        type="number"
        step="0.01"
        min="0"
        value={monto_liquidado}
        onChange={(evento) => set_monto_liquidado(evento.target.value)}
      />
      <Boton
        variante="primario"
        onClick={() => mutacion.mutate()}
        disabled={mutacion.isPending || !monto_liquidado}
      >
        {liquidacion ? "Guardar corrección" : "Registrar liquidación recibida"}
      </Boton>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto={liquidacion ? "No se pudo corregir." : "No se pudo registrar."}
      />
    </div>
  );
}

function FormularioConciliarPago({
  cuenta_id,
  adicional,
  liquidacion = null,
  al_corregir,
}: {
  cuenta_id: number;
  adicional: boolean;
  // Con la liquidacion ya pagada, el formulario corrige el pago.
  liquidacion?: Liquidacion | null;
  al_corregir?: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [monto_pagado, set_monto_pagado] = useState(String(liquidacion?.monto_pagado ?? ""));

  const mutacion = useMutation({
    mutationFn: async () => {
      if (liquidacion) await corregir_pago(cuenta_id, monto_pagado);
      else await conciliar_pago(cuenta_id, monto_pagado);
    },
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      if (liquidacion) al_corregir?.();
      else set_monto_pagado("");
    },
  });

  return (
    <div className={estilos.fila_accion}>
      <CampoTexto
        etiqueta={adicional ? "Monto del pago adicional" : "Monto que pagó la IAFAS"}
        obligatorio
        type="number"
        step="0.01"
        min="0"
        value={monto_pagado}
        onChange={(evento) => set_monto_pagado(evento.target.value)}
      />
      <Boton
        variante="primario"
        onClick={() => mutacion.mutate()}
        disabled={mutacion.isPending || !monto_pagado}
      >
        {liquidacion ? "Guardar corrección" : "Registrar pago y conciliar"}
      </Boton>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto={liquidacion ? "No se pudo corregir." : "No se pudo conciliar."}
      />
    </div>
  );
}

// T-10 y T-11 (Tabla 58): la IAFAS liquida una cuenta en auditoria o ya
// subsanada (o la porcion no observada de una glosa parcial), y paga una
// cuenta ya liquidada. Fuera de esos estados no hay nada que registrar, y
// la pantalla dice por que en vez de ofrecer un formulario que el motor
// rechazaria.
const _LIQUIDABLES = new Set(["EN_AUDITORIA", "SUBSANADA", "GLOSADA_PARCIAL"]);
const _PAGABLES = new Set(["LIQUIDADA", "LIQUIDADA_PARCIAL"]);
// Una cuenta pagada de menos admite pagos adicionales hasta cerrar la diferencia.
const _PAGADAS = new Set(["PAGADA", "PAGADA_PARCIAL"]);

function falta_por_pagar(estado: string, liquidacion: Liquidacion): boolean {
  return _PAGADAS.has(estado) && Number(liquidacion.diferencia ?? 0) < 0;
}

function CorregirLiquidacion({
  cuenta_id,
  liquidacion,
}: {
  cuenta_id: number;
  liquidacion: Liquidacion;
}) {
  const [abierto, set_abierto] = useState(false);
  if (!abierto) {
    return (
      <Boton variante="terciario" onClick={() => set_abierto(true)}>
        Corregir liquidación
      </Boton>
    );
  }
  return (
    <FormularioRegistrarLiquidacion
      cuenta_id={cuenta_id}
      liquidacion={liquidacion}
      al_corregir={() => set_abierto(false)}
    />
  );
}

function CorregirPago({ cuenta_id, liquidacion }: { cuenta_id: number; liquidacion: Liquidacion }) {
  const [abierto, set_abierto] = useState(false);
  if (!abierto) {
    return (
      <Boton variante="terciario" onClick={() => set_abierto(true)}>
        Corregir pago
      </Boton>
    );
  }
  return (
    <FormularioConciliarPago
      cuenta_id={cuenta_id}
      adicional={false}
      liquidacion={liquidacion}
      al_corregir={() => set_abierto(false)}
    />
  );
}

function FormulariosTesoreria({
  cuenta_id,
  estado,
  liquidacion,
}: {
  cuenta_id: number;
  estado: string;
  liquidacion: Liquidacion | null;
}) {
  const { sesion } = usar_sesion();
  if (!sesion?.roles.includes("tesoreria")) return null;
  // La liquidacion y el pago que la IAFAS comunica se registran solos: el
  // formulario queda para lo que llegue por otro medio.
  if (liquidacion === null) {
    if (!_LIQUIDABLES.has(estado)) return null;
    return (
      <RegistroManual rotulo="Registrar liquidación">
        <FormularioRegistrarLiquidacion cuenta_id={cuenta_id} />
      </RegistroManual>
    );
  }
  const adicional = Boolean(liquidacion.conciliado_en);
  const pagable = adicional ? falta_por_pagar(estado, liquidacion) : _PAGABLES.has(estado);
  return (
    <>
      {/* Solo la registrada a mano, mientras el servidor la admita. */}
      {liquidacion.corregible ? (
        <CorregirLiquidacion cuenta_id={cuenta_id} liquidacion={liquidacion} />
      ) : null}
      {liquidacion.pago_corregible ? (
        <CorregirPago cuenta_id={cuenta_id} liquidacion={liquidacion} />
      ) : null}
      {pagable ? (
        <RegistroManual rotulo={adicional ? "Registrar pago adicional" : "Registrar pago"}>
          <FormularioConciliarPago cuenta_id={cuenta_id} adicional={adicional} />
        </RegistroManual>
      ) : null}
    </>
  );
}

function tiene_acceso_lectura(sesion: ReturnType<typeof usar_sesion>["sesion"]): boolean {
  if (!sesion) return false;
  const roles_lectura = ["analista", "auditor", "jefe", "tesoreria"] as const;
  return roles_lectura.some((rol) => sesion.roles.includes(rol));
}

export function SeccionLiquidacion({ cuenta_id, estado }: { cuenta_id: number; estado: string }) {
  const { sesion } = usar_sesion();
  const consulta = usar_liquidacion_cuenta(cuenta_id);
  const facturado = usar_total_facturado(cuenta_id);
  const copago = usar_filas_copago(cuenta_id, estado);

  if (!tiene_acceso_lectura(sesion) || consulta.isPending) return null;

  const liquidacion = consulta.data ?? null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Liquidación y pago de la IAFAS</div>
      <DatosLiquidacion facturado={facturado} copago={copago} liquidacion={liquidacion} />
      <FormulariosTesoreria cuenta_id={cuenta_id} estado={estado} liquidacion={liquidacion} />
    </div>
  );
}
