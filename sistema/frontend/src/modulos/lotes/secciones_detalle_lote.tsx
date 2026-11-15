import { useMutation } from "@tanstack/react-query";
import {
  obtener_archivo_s01_lote,
  type DetalleLote,
  type ObservacionOficial,
  type ResumenAcuse,
} from "../../api/lotes";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { IconoCheck, IconoDescarga } from "./iconos_detalle_lote";
import estilos from "./detalle_lote.module.css";

const _COLUMNAS_OBSERVACIONES: ColumnaTabla<ObservacionOficial>[] = [
  { clave: "tabla", encabezado: "Tabla" },
  { clave: "numero_linea", encabezado: "Línea", alinear_derecha: true },
  { clave: "campo", encabezado: "Campo" },
  { clave: "valor_observado", encabezado: "Valor observado" },
  { clave: "codigo_error", encabezado: "Código" },
  { clave: "descripcion", encabezado: "Descripción" },
];

const _COLUMNAS_ACUSES: ColumnaTabla<ResumenAcuse>[] = [
  { clave: "resultado_transferencia", encabezado: "Resultado" },
  {
    clave: "intentado_en",
    encabezado: "Intentado",
    formatear: (fila) => formatear_fecha_hora(fila.intentado_en),
  },
  { clave: "respuesta_receptor", encabezado: "Respuesta de la IAFAS" },
  {
    clave: "respondido_en",
    encabezado: "Respondido",
    formatear: (fila) => (fila.respondido_en ? formatear_fecha_hora(fila.respondido_en) : "—"),
  },
];

function descargar_blob(blob: Blob, nombre_archivo: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre_archivo;
  enlace.click();
  URL.revokeObjectURL(url);
}

function AccionDescargarS01({
  lote_id,
  nombre_archivo,
}: {
  lote_id: number;
  nombre_archivo: string;
}) {
  const mutacion = useMutation({
    mutationFn: async () => descargar_blob(await obtener_archivo_s01_lote(lote_id), nombre_archivo),
  });

  return (
    <div>
      <button
        type="button"
        className={estilos.enlace_descarga}
        onClick={() => mutacion.mutate()}
        disabled={mutacion.isPending}
      >
        <IconoDescarga />
        {nombre_archivo}
      </button>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo descargar el archivo."
      />
    </div>
  );
}

export function SeccionDatosLote({
  lote,
  nombre_iafas,
}: {
  lote: DetalleLote;
  nombre_iafas: string;
}) {
  const datos = [
    { etiqueta: "Periodo", valor: lote.periodo },
    { etiqueta: "IAFAS", valor: nombre_iafas },
    { etiqueta: "Cantidad de documentos", valor: String(lote.cantidad_documentos) },
    { etiqueta: "Generado", valor: formatear_fecha_hora(lote.generado_en) },
    // RT-06: con que version del estandar y del diccionario de mapeo se genero.
    { etiqueta: "Estándar TEDEF", valor: lote.version_esquema_tedef ?? "—" },
    { etiqueta: "Diccionario de mapeo", valor: lote.version_mapeo?.slice(0, 12) ?? "—" },
  ];
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Datos del lote</div>
      <div className={estilos.rejilla}>
        {datos.map((dato) => (
          <div key={dato.etiqueta} className={estilos.campo_dato}>
            <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
            <span>{dato.valor}</span>
          </div>
        ))}
        <div className={estilos.campo_dato}>
          <span className={estilos.etiqueta_dato}>Archivo .S01</span>
          {lote.nombre_s01 ? (
            <AccionDescargarS01 lote_id={lote.id} nombre_archivo={lote.nombre_s01} />
          ) : (
            <span>—</span>
          )}
        </div>
      </div>
    </div>
  );
}

function EstadoVacioCompacto({ texto }: { texto: string }) {
  return (
    <div className={estilos.vacio_compacto}>
      <IconoCheck />
      <span>{texto}</span>
    </div>
  );
}

export function SeccionObservaciones({ observaciones }: { observaciones: ObservacionOficial[] }) {
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Observaciones del validador</div>
      {observaciones.length === 0 ? (
        <EstadoVacioCompacto texto="Sin observaciones pendientes." />
      ) : (
        <TablaDatos
          columnas={_COLUMNAS_OBSERVACIONES}
          filas={observaciones}
          obtener_clave={(fila, indice) => `${fila.tabla}-${fila.numero_linea}-${indice}`}
          mensaje_vacio="No hay observaciones registradas."
        />
      )}
    </div>
  );
}

export function SeccionAcuses({ acuses }: { acuses: ResumenAcuse[] }) {
  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Acuses de transmisión</div>
      {acuses.length === 0 ? (
        <EstadoVacioCompacto texto="Sin acuses de transmisión registrados." />
      ) : (
        <TablaDatos
          columnas={_COLUMNAS_ACUSES}
          filas={acuses}
          obtener_clave={(fila) => fila.id}
          mensaje_vacio="No hay acuses registrados."
        />
      )}
    </div>
  );
}
