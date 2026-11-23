import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ComunicacionIafas } from "../../api/comunicaciones_iafas";
import { listar_correos_iafas } from "../../api/correos_iafas";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import {
  tiene_acceso_observaciones,
  usar_descripciones_motivos,
} from "../observaciones/usar_observaciones";
import { TIPOS_COMUNICACION } from "./columnas_comunicaciones";
import { DialogoCorreo } from "./dialogo_correo";
import { usar_nombre_aseguradora } from "./usar_nombre_aseguradora";
import estilos from "./comunicaciones.module.css";

// El mensaje original de una comunicacion registrada (2026-11-22): el
// correo que la trajo o lo que la IAFAS publico en su portal.

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <>
      <dt>{etiqueta}</dt>
      <dd>{children}</dd>
    </>
  );
}

function texto(datos: Record<string, unknown>, clave: string): string | null {
  const dato = datos[clave];
  return typeof dato === "string" && dato ? dato : null;
}

function DatosPublicados({ comunicacion }: { comunicacion: ComunicacionIafas }) {
  const { sesion } = usar_sesion();
  const motivos = usar_descripciones_motivos(tiene_acceso_observaciones(sesion));
  const datos = comunicacion.datos;
  const motivo = texto(datos, "motivo_codigo");
  const montos: [string, string][] = [
    ["Monto glosado", "monto_glosado"],
    ["Monto liquidado", "monto_liquidado"],
    ["Monto pagado", "monto_pagado"],
  ];
  return (
    <>
      {motivo ? <Dato etiqueta="Motivo">{motivos.get(motivo) ?? motivo}</Dato> : null}
      {comunicacion.tipo === "OBSERVACION" ? (
        <Dato etiqueta="Alcance">{datos.es_parcial === true ? "Parcial" : "Total"}</Dato>
      ) : null}
      {montos.map(([etiqueta, clave]) =>
        texto(datos, clave) ? (
          <Dato key={clave} etiqueta={etiqueta}>
            {formatear_monto(texto(datos, clave) ?? "")}
          </Dato>
        ) : null,
      )}
      {texto(datos, "detalle") ? <Dato etiqueta="Detalle">{texto(datos, "detalle")}</Dato> : null}
    </>
  );
}

function PublicacionPortal({
  comunicacion,
  al_cerrar,
}: {
  comunicacion: ComunicacionIafas;
  al_cerrar: () => void;
}) {
  const nombre_aseguradora = usar_nombre_aseguradora();
  return (
    <Dialogo
      titulo="Publicación en el portal de la IAFAS"
      al_cerrar={al_cerrar}
      acciones={
        <Boton variante="secundario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      <dl className={estilos.ficha}>
        <Dato etiqueta="IAFAS">{nombre_aseguradora(comunicacion.codigo_iafas)}</Dato>
        <Dato etiqueta="Código">{comunicacion.codigo}</Dato>
        <Dato etiqueta="Recibida">{formatear_fecha_hora(comunicacion.recibida_en)}</Dato>
        <Dato etiqueta="Comunicación">
          {TIPOS_COMUNICACION[comunicacion.tipo] ?? comunicacion.tipo}
        </Dato>
        <Dato etiqueta="Comprobante">{comunicacion.documento}</Dato>
        <DatosPublicados comunicacion={comunicacion} />
        <Dato etiqueta="Cuenta">
          {comunicacion.cuenta_medica_id ? (
            <Link to={`/cuentas/${comunicacion.cuenta_medica_id}`}>
              {comunicacion.identificacion_interna ?? comunicacion.cuenta_medica_id}
            </Link>
          ) : (
            "—"
          )}
        </Dato>
      </dl>
    </Dialogo>
  );
}

interface Propiedades {
  comunicacion: ComunicacionIafas;
  al_cerrar: () => void;
}

export function DialogoComunicacion({ comunicacion, al_cerrar }: Propiedades) {
  const por_correo = comunicacion.canal === "CORREO";
  const correos = useQuery({
    queryKey: ["correos_iafas", "TODOS", 0],
    queryFn: () => listar_correos_iafas({}),
    enabled: por_correo,
  });
  if (por_correo && correos.isPending) return null;
  const correo = correos.data?.find((fila) => fila.comunicacion_codigo === comunicacion.codigo);
  return correo ? (
    <DialogoCorreo correo_id={correo.id} al_cerrar={al_cerrar} />
  ) : (
    <PublicacionPortal comunicacion={comunicacion} al_cerrar={al_cerrar} />
  );
}
