import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  actualizar_parametros_iafas,
  listar_parametros_iafas,
  type ParametrosIafas,
} from "../../api/parametros";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { con_unidad } from "./formato_administracion";
import estilos from "./administracion.module.css";

// CU-18: plazos del convenio con cada aseguradora (Tabla 61) y ventanas de
// monitoreo (Seccion 8.3), en su propia pantalla (rediseno 2026-11-15).
type CampoPlazo = Exclude<keyof ParametrosIafas, "iafas_id" | "codigo" | "razon_social">;

interface DefinicionPlazo {
  clave: CampoPlazo;
  encabezado: string;
  singular: string;
  plural: string;
}

const _PLAZOS: DefinicionPlazo[] = [
  {
    clave: "dias_plazo_respuesta_observacion",
    encabezado: "Respuesta a observaciones",
    singular: "día",
    plural: "días",
  },
  {
    clave: "dias_plazo_comunicacion_auditoria",
    encabezado: "Resultado de auditoría",
    singular: "día",
    plural: "días",
  },
  {
    clave: "dias_plazo_pago_liquidacion",
    encabezado: "Pago de liquidación",
    singular: "día",
    plural: "días",
  },
  {
    clave: "ventana_monitoreo_horas",
    encabezado: "Monitoreo de respuestas",
    singular: "hora",
    plural: "horas",
  },
  {
    clave: "periodicidad_remision_dias",
    encabezado: "Frecuencia de remisión",
    singular: "día",
    plural: "días",
  },
];

function columnas(al_editar: (fila: ParametrosIafas) => void): ColumnaTabla<ParametrosIafas>[] {
  return [
    {
      clave: "razon_social",
      encabezado: "Aseguradora",
      formatear: (fila) => (
        <>
          {fila.razon_social}
          <span className={estilos.dato_secundario}>Código {fila.codigo}</span>
        </>
      ),
    },
    ..._PLAZOS.map(({ clave, encabezado, singular, plural }) => ({
      clave,
      encabezado,
      formatear: (fila: ParametrosIafas) => con_unidad(fila[clave], singular, plural),
    })),
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

function usar_guardar_plazos(
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

function DialogoPlazos({ iafas, al_cerrar }: { iafas: ParametrosIafas; al_cerrar: () => void }) {
  const [valores, set_valores] = useState(() =>
    Object.fromEntries(_PLAZOS.map(({ clave }) => [clave, String(iafas[clave])])),
  );
  const mutacion = usar_guardar_plazos(iafas.iafas_id, valores, al_cerrar);
  const validos = Object.values(valores).every((valor) => Number(valor) >= 1);
  return (
    <Dialogo
      titulo={`Plazos con ${iafas.razon_social}`}
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
      {_PLAZOS.map(({ clave, encabezado, plural }) => (
        <CampoTexto
          key={clave}
          etiqueta={`${encabezado} (${plural})`}
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

export function AdministracionAseguradoras() {
  const consulta = useQuery({
    queryKey: ["administracion", "parametros", "iafas"],
    queryFn: listar_parametros_iafas,
  });
  const [editando, set_editando] = useState<ParametrosIafas | null>(null);

  return (
    <div>
      <TituloPagina titulo="Aseguradoras" />
      <div className={estilos.seccion}>
        <div className={estilos.titulo_seccion}>Plazos del convenio</div>
        <div className={estilos.tabla_plazos}>
          <TablaDatos
            columnas={columnas(set_editando)}
            filas={consulta.data ?? []}
            obtener_clave={(fila) => fila.iafas_id}
            cargando={consulta.isPending}
            error={consulta.error}
            mensaje_vacio="No hay aseguradoras registradas."
          />
        </div>
      </div>
      {editando ? <DialogoPlazos iafas={editando} al_cerrar={() => set_editando(null)} /> : null}
    </div>
  );
}
