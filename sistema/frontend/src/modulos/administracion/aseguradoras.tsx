import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  actualizar_parametros_iafas,
  crear_iafas,
  eliminar_iafas,
  listar_parametros_iafas,
  type ParametrosIafas,
  type SolicitudNuevaIafas,
} from "../../api/parametros";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { con_unidad } from "./formato_administracion";
import { SeccionRemitentes } from "./seccion_remitentes";
import estilos from "./administracion.module.css";

// CU-18: plazos del convenio con cada aseguradora (Tabla 61) y ventanas de
// monitoreo (Seccion 8.3), en su propia pantalla (rediseno 2026-11-15).
type CampoPlazo = Exclude<
  keyof ParametrosIafas,
  "iafas_id" | "codigo" | "razon_social" | "correo_remitente"
>;

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

function columnas(
  al_editar: (fila: ParametrosIafas) => void,
  al_eliminar: (fila: ParametrosIafas) => void,
): ColumnaTabla<ParametrosIafas>[] {
  return [
    {
      clave: "razon_social",
      encabezado: "IAFAS",
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
        <div className={estilos.acciones_fila}>
          <Boton variante="terciario" onClick={() => al_editar(fila)}>
            Editar
          </Boton>
          <Boton variante="terciario" onClick={() => al_eliminar(fila)}>
            Eliminar
          </Boton>
        </div>
      ),
    },
  ];
}

function usar_guardar_plazos(
  iafas_id: number | null,
  valores: Record<string, string>,
  al_cerrar: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () => {
      const { codigo = "", razon_social = "", ...plazos } = valores;
      const numericos = Object.fromEntries(
        Object.entries(plazos).map(([clave, valor]) => [clave, Number(valor)]),
      );
      // Sin aseguradora es un alta: lleva ademas el codigo y la razon social.
      // Al editar, el codigo no cambia: identifica a la aseguradora ante SUSALUD.
      return iafas_id === null
        ? crear_iafas({ codigo, razon_social, ...numericos } as SolicitudNuevaIafas)
        : actualizar_parametros_iafas(iafas_id, { razon_social, ...numericos });
    },
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["administracion", "parametros"] });
      al_cerrar();
    },
  });
}

interface Identidad {
  codigo: string;
  razon_social: string;
}

function CamposIdentidad({
  identidad,
  al_cambiar,
  codigo_fijo,
}: {
  identidad: Identidad;
  al_cambiar: (identidad: Identidad) => void;
  codigo_fijo: boolean;
}) {
  return (
    <>
      <CampoTexto
        etiqueta="Código"
        obligatorio
        maxLength={5}
        disabled={codigo_fijo}
        error={codigo_fijo ? undefined : error_codigo(identidad.codigo)}
        value={identidad.codigo}
        onChange={(evento) => al_cambiar({ ...identidad, codigo: evento.target.value })}
      />
      <CampoTexto
        etiqueta="Razón social"
        obligatorio
        maxLength={200}
        value={identidad.razon_social}
        onChange={(evento) => al_cambiar({ ...identidad, razon_social: evento.target.value })}
      />
    </>
  );
}

function identidad_de(iafas: ParametrosIafas | null): Identidad {
  return { codigo: iafas?.codigo ?? "", razon_social: iafas?.razon_social ?? "" };
}

function valores_iniciales(iafas: ParametrosIafas | null): Record<string, string> {
  return Object.fromEntries(_PLAZOS.map(({ clave }) => [clave, iafas ? String(iafas[clave]) : ""]));
}

// Los mismos maximos que el servidor: dias, un anio; horas, una semana.
function maximo_de(plural: string): number {
  return plural === "horas" ? 168 : 365;
}

// Por que un campo no cumple, bajo el mismo campo; vacio, solo el asterisco.
function error_plazo(valor: string | undefined, plural: string): string | undefined {
  if (!valor) return undefined;
  const numero = Number(valor);
  const maximo = maximo_de(plural);
  return Number.isInteger(numero) && numero >= 1 && numero <= maximo
    ? undefined
    : `Debe estar entre 1 y ${maximo} ${plural}.`;
}

// El codigo de la IAFAS va en el nombre de los archivos del lote.
const _CODIGO_VALIDO = /^\d{5}$/;

function error_codigo(codigo: string): string | undefined {
  return codigo === "" || _CODIGO_VALIDO.test(codigo.trim())
    ? undefined
    : "Debe tener cinco dígitos.";
}

// Ademas de los plazos se exigen el codigo de cinco digitos y la razon social.
function son_validos(
  valores: Record<string, string>,
  identidad: Identidad,
  codigo_fijo: boolean,
): boolean {
  const plazos = _PLAZOS.every(
    ({ clave, plural }) => Boolean(valores[clave]) && !error_plazo(valores[clave], plural),
  );
  const codigo = codigo_fijo || _CODIGO_VALIDO.test(identidad.codigo.trim());
  return plazos && codigo && identidad.razon_social.trim() !== "";
}

interface PropiedadesDialogoPlazos {
  iafas: ParametrosIafas | null;
  al_cerrar: () => void;
}

function DialogoPlazos({ iafas, al_cerrar }: PropiedadesDialogoPlazos) {
  const [valores, set_valores] = useState(() => valores_iniciales(iafas));
  const [identidad, set_identidad] = useState(() => identidad_de(iafas));
  const mutacion = usar_guardar_plazos(
    iafas?.iafas_id ?? null,
    { ...valores, ...identidad },
    al_cerrar,
  );
  const validos = son_validos(valores, identidad, iafas !== null);
  return (
    <Dialogo
      titulo={iafas ? `Plazos con ${iafas.razon_social}` : "Nueva IAFAS"}
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
      <CamposIdentidad
        identidad={identidad}
        al_cambiar={set_identidad}
        codigo_fijo={iafas !== null}
      />
      {_PLAZOS.map(({ clave, encabezado, plural }) => (
        <CampoTexto
          key={clave}
          etiqueta={`${encabezado} (${plural})`}
          obligatorio
          type="number"
          min="1"
          max={String(maximo_de(plural))}
          error={error_plazo(valores[clave], plural)}
          value={valores[clave]}
          onChange={(evento) => set_valores({ ...valores, [clave]: evento.target.value })}
        />
      ))}
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudieron guardar." />
    </Dialogo>
  );
}

function DialogoEliminar({ iafas, al_cerrar }: { iafas: ParametrosIafas; al_cerrar: () => void }) {
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: () => eliminar_iafas(iafas.iafas_id),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["administracion", "parametros"] });
      al_cerrar();
    },
  });
  return (
    <Dialogo
      titulo="Eliminar IAFAS"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="destructivo"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending}
          >
            Eliminar
          </Boton>
        </>
      }
    >
      <p>
        Se eliminará {iafas.razon_social} (código {iafas.codigo}). Esta acción no se puede deshacer.
      </p>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo eliminar." />
    </Dialogo>
  );
}

export function AdministracionAseguradoras() {
  const consulta = useQuery({
    queryKey: ["administracion", "parametros", "iafas"],
    queryFn: listar_parametros_iafas,
  });
  const [editando, set_editando] = useState<ParametrosIafas | null>(null);
  const [creando, set_creando] = useState(false);
  const [eliminando, set_eliminando] = useState<ParametrosIafas | null>(null);

  return (
    <div>
      <TituloPagina
        titulo="IAFAS"
        acciones={
          <Boton variante="primario" onClick={() => set_creando(true)}>
            Nueva IAFAS
          </Boton>
        }
      />
      <div className={estilos.seccion}>
        <div className={estilos.titulo_seccion}>Plazos del convenio</div>
        <div className={estilos.tabla_plazos}>
          <TablaDatos
            columnas={columnas(set_editando, set_eliminando)}
            filas={consulta.data ?? []}
            obtener_clave={(fila) => fila.iafas_id}
            cargando={consulta.isPending}
            error={consulta.error}
            mensaje_vacio="No hay IAFAS registradas."
          />
        </div>
      </div>
      <SeccionRemitentes
        filas={consulta.data ?? []}
        cargando={consulta.isPending}
        error={consulta.error}
      />
      {editando ? <DialogoPlazos iafas={editando} al_cerrar={() => set_editando(null)} /> : null}
      {creando ? <DialogoPlazos iafas={null} al_cerrar={() => set_creando(false)} /> : null}
      {eliminando ? (
        <DialogoEliminar iafas={eliminando} al_cerrar={() => set_eliminando(null)} />
      ) : null}
    </div>
  );
}
