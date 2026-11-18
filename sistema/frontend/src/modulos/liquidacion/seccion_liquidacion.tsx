import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { consultar_documentos_pago } from "../../api/comprobante";
import { conciliar_pago, registrar_liquidacion, type Liquidacion } from "../../api/liquidacion";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { RegistroManual } from "../../componentes_base/registro_manual";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { usar_liquidacion_cuenta } from "./usar_liquidacion";

// Lo facturado a la IAFAS, como referencia de lo que liquida y paga
// (2026-11-18): es el total del comprobante vigente.
function usar_total_facturado(cuenta_id: number): string | null {
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "comprobante"],
    queryFn: () => consultar_documentos_pago(cuenta_id),
  });
  const total = consulta.data?.vigente.total;
  return total != null ? formatear_monto(total) : null;
}

function DatosLiquidacion({
  facturado,
  liquidacion,
}: {
  facturado: string | null;
  liquidacion: Liquidacion | null;
}) {
  const monto = (valor: string | null | undefined) => (valor ? formatear_monto(valor) : "—");
  const conciliado_en = liquidacion?.conciliado_en;
  const datos = [
    { etiqueta: "Total facturado", valor: facturado ?? "—" },
    { etiqueta: "Liquidado por la IAFAS", valor: monto(liquidacion?.monto_liquidado) },
    { etiqueta: "Pagado por la IAFAS", valor: monto(liquidacion?.monto_pagado) },
    { etiqueta: "Diferencia", valor: monto(liquidacion?.diferencia) },
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

function FormularioRegistrarLiquidacion({ cuenta_id }: { cuenta_id: number }) {
  const cliente_consultas = useQueryClient();
  const [monto_liquidado, set_monto_liquidado] = useState("");

  const mutacion = useMutation({
    mutationFn: () => registrar_liquidacion(cuenta_id, monto_liquidado),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      set_monto_liquidado("");
    },
  });

  return (
    <div className={estilos.fila_accion}>
      <CampoTexto
        etiqueta="Monto que liquidó la IAFAS"
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
        Registrar liquidación recibida
      </Boton>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo registrar." />
    </div>
  );
}

function FormularioConciliarPago({ cuenta_id }: { cuenta_id: number }) {
  const cliente_consultas = useQueryClient();
  const [monto_pagado, set_monto_pagado] = useState("");

  const mutacion = useMutation({
    mutationFn: () => conciliar_pago(cuenta_id, monto_pagado),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      set_monto_pagado("");
    },
  });

  return (
    <div className={estilos.fila_accion}>
      <CampoTexto
        etiqueta="Monto que pagó la IAFAS"
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
        Registrar pago y conciliar
      </Boton>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo conciliar." />
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
      <RegistroManual>
        <FormularioRegistrarLiquidacion cuenta_id={cuenta_id} />
      </RegistroManual>
    );
  }
  if (liquidacion.conciliado_en || !_PAGABLES.has(estado)) return null;
  return (
    <RegistroManual>
      <FormularioConciliarPago cuenta_id={cuenta_id} />
    </RegistroManual>
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

  if (!tiene_acceso_lectura(sesion) || consulta.isPending) return null;

  const liquidacion = consulta.data ?? null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Liquidación y pago de la IAFAS</div>
      <DatosLiquidacion facturado={facturado} liquidacion={liquidacion} />
      <FormulariosTesoreria cuenta_id={cuenta_id} estado={estado} liquidacion={liquidacion} />
    </div>
  );
}
