import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  actualizar_parametros_iafas,
  listar_parametros_iafas,
  listar_parametros_sistema,
  type ParametroSistema,
  type ParametrosIafas,
} from "../../api/parametros";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import estilos from "./administracion.module.css";

// CU-18: plazos por convenio con cada IAFAS (Tabla 61) y ventanas (Seccion
// 8.3), editables; los parametros del sistema se fijan en el despliegue.
type CampoParametro = Exclude<keyof ParametrosIafas, "iafas_id" | "codigo" | "razon_social">;

const _CAMPOS: { clave: CampoParametro; encabezado: string }[] = [
  { clave: "dias_plazo_respuesta_observacion", encabezado: "Respuesta a observación (días)" },
  { clave: "dias_plazo_comunicacion_auditoria", encabezado: "Resultado de auditoría (días)" },
  { clave: "dias_plazo_pago_liquidacion", encabezado: "Pago de liquidación (días)" },
  { clave: "ventana_monitoreo_horas", encabezado: "Ventana de monitoreo (horas)" },
  { clave: "periodicidad_remision_dias", encabezado: "Periodicidad de remisión (días)" },
];

const _COLUMNAS_SISTEMA: ColumnaTabla<ParametroSistema>[] = [
  { clave: "clave", encabezado: "Parámetro" },
  { clave: "valor", encabezado: "Valor" },
];

function columnas_iafas(
  al_editar: (fila: ParametrosIafas) => void,
): ColumnaTabla<ParametrosIafas>[] {
  return [
    { clave: "codigo", encabezado: "IAFAS", formatear: (f) => `${f.codigo} — ${f.razon_social}` },
    ..._CAMPOS.map(({ clave, encabezado }) => ({ clave, encabezado, alinear_derecha: true })),
    {
      clave: "iafas_id",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_editar(fila)}>
          Editar
        </Boton>
      ),
    },
  ];
}

function usar_guardar_parametros(
  iafas_id: number,
  valores: Record<string, string>,
  al_cerrar: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () =>
      actualizar_parametros_iafas(
        iafas_id,
        Object.fromEntries(Object.entries(valores).map(([clave, valor]) => [clave, Number(valor)])),
      ),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["administracion", "parametros"] });
      al_cerrar();
    },
  });
}

function DialogoParametros({
  iafas,
  al_cerrar,
}: {
  iafas: ParametrosIafas;
  al_cerrar: () => void;
}) {
  const [valores, set_valores] = useState(() =>
    Object.fromEntries(_CAMPOS.map(({ clave }) => [clave, String(iafas[clave])])),
  );
  const mutacion = usar_guardar_parametros(iafas.iafas_id, valores, al_cerrar);
  const validos = Object.values(valores).every((valor) => Number(valor) >= 1);
  return (
    <Dialogo
      titulo={`Parámetros de ${iafas.razon_social}`}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={!validos || mutacion.isPending}
          >
            Guardar
          </Boton>
        </>
      }
    >
      {_CAMPOS.map(({ clave, encabezado }) => (
        <CampoTexto
          key={clave}
          etiqueta={encabezado}
          type="number"
          min="1"
          max="365"
          value={valores[clave]}
          onChange={(evento) => set_valores({ ...valores, [clave]: evento.target.value })}
        />
      ))}
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudieron guardar." />
    </Dialogo>
  );
}

export function SeccionParametros() {
  const iafas = useQuery({
    queryKey: ["administracion", "parametros", "iafas"],
    queryFn: listar_parametros_iafas,
  });
  const sistema = useQuery({
    queryKey: ["administracion", "parametros", "sistema"],
    queryFn: listar_parametros_sistema,
  });
  const [editando, set_editando] = useState<ParametrosIafas | null>(null);

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Parámetros</div>
      <TablaDatos
        columnas={columnas_iafas(set_editando)}
        filas={iafas.data ?? []}
        obtener_clave={(fila) => fila.iafas_id}
        cargando={iafas.isPending}
        error={iafas.error}
        mensaje_vacio="No hay IAFAS registradas."
      />
      <TablaDatos
        columnas={_COLUMNAS_SISTEMA}
        filas={sistema.data ?? []}
        obtener_clave={(fila) => fila.clave}
        cargando={sistema.isPending}
        error={sistema.error}
        mensaje_vacio="Sin parámetros del sistema."
      />
      {editando ? (
        <DialogoParametros iafas={editando} al_cerrar={() => set_editando(null)} />
      ) : null}
    </div>
  );
}
