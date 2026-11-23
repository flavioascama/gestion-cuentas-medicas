import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import {
  consultar_correo_iafas,
  descargar_adjunto_correo,
  descartar_correo_iafas,
  vincular_correo_iafas,
  type AdjuntoCorreo,
  type CorreoIafasDetalle,
} from "../../api/correos_iafas";
import type { ResumenCuenta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { guardar_archivo } from "../../utilidades/archivo";
import { formatear_fecha_hora } from "../../utilidades/formato";
import { BuscadorCuenta } from "../cuentas/buscador_cuenta";
import { MOTIVOS_OMISION, MOTIVOS_REVISION } from "./etiquetas_correos";
import { RespuestasCorreo } from "./respuestas_correo";
import { usar_nombre_aseguradora } from "./usar_nombre_aseguradora";
import estilos from "./comunicaciones.module.css";

// Detalle de un correo recibido: remitente, asunto, texto y adjuntos. El
// analista y el jefe vinculan a una cuenta el correo por revisar o lo
// descartan con un motivo.

const _REVISA = ["analista", "jefe"];

function formatear_tamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FilaAdjunto({ correo_id, adjunto }: { correo_id: number; adjunto: AdjuntoCorreo }) {
  const descarga = useMutation({
    mutationFn: () => descargar_adjunto_correo(correo_id, adjunto.id),
    onSuccess: (blob) => guardar_archivo(blob, adjunto.nombre),
  });
  return (
    <li className={estilos.adjunto}>
      <span className={estilos.nombre_adjunto}>{adjunto.nombre}</span>
      <span className={estilos.dato_secundario}>{formatear_tamano(adjunto.tamano)}</span>
      {adjunto.almacenado ? (
        <Boton variante="terciario" onClick={() => descarga.mutate()} disabled={descarga.isPending}>
          Descargar
        </Boton>
      ) : (
        <span className={estilos.dato_secundario}>
          No almacenado: {MOTIVOS_OMISION[adjunto.motivo_omision ?? ""] ?? "no disponible"}
        </span>
      )}
      <MensajeErrorMutacion error={descarga.error} texto_por_defecto="No se pudo descargar." />
    </li>
  );
}

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <>
      <dt>{etiqueta}</dt>
      <dd>{children}</dd>
    </>
  );
}

function resolucion(correo: CorreoIafasDetalle): string | null {
  if (!correo.resuelto_por || !correo.resuelto_en) return null;
  const hecho = `${correo.resuelto_por}, ${formatear_fecha_hora(correo.resuelto_en)}`;
  return correo.nota_resolucion ? `${hecho}. Motivo: ${correo.nota_resolucion}` : hecho;
}

function ContenidoCorreo({ correo }: { correo: CorreoIafasDetalle }) {
  const revisado = resolucion(correo);
  const nombre_aseguradora = usar_nombre_aseguradora();
  return (
    <>
      <dl className={estilos.ficha}>
        <Dato etiqueta="Remitente">{correo.remitente}</Dato>
        <Dato etiqueta="Recibido">{formatear_fecha_hora(correo.recibido_en)}</Dato>
        <Dato etiqueta="IAFAS">
          {correo.codigo_iafas ? nombre_aseguradora(correo.codigo_iafas) : "—"}
        </Dato>
        <Dato etiqueta="Estado">
          <EtiquetaEstado estado={correo.estado} />
          {correo.motivo_revision ? (
            <span className={estilos.dato_secundario}>
              {MOTIVOS_REVISION[correo.motivo_revision] ?? correo.motivo_revision}
            </span>
          ) : null}
        </Dato>
        {correo.identificacion_interna ? (
          <Dato etiqueta="Cuenta">{correo.identificacion_interna}</Dato>
        ) : null}
        {revisado ? <Dato etiqueta="Revisado por">{revisado}</Dato> : null}
      </dl>
      <div className={estilos.asunto}>{correo.asunto || "(Sin asunto)"}</div>
      <pre className={estilos.texto_correo}>{correo.texto || "(Sin texto)"}</pre>
      {correo.adjuntos.length > 0 ? (
        <ul className={estilos.adjuntos}>
          {correo.adjuntos.map((adjunto) => (
            <FilaAdjunto key={adjunto.id} correo_id={correo.id} adjunto={adjunto} />
          ))}
        </ul>
      ) : null}
      <RespuestasCorreo correo_id={correo.id} />
      <div className={estilos.huella}>Huella de integridad: {correo.huella}</div>
    </>
  );
}

interface PropiedadesResolver {
  correo_id: number;
  al_terminar: () => Promise<void>;
}

function VincularCorreo({
  correo_id,
  codigo_iafas,
  al_terminar,
}: PropiedadesResolver & { codigo_iafas: string | null }) {
  const [cuenta, set_cuenta] = useState<ResumenCuenta | null>(null);
  const vinculacion = useMutation({
    mutationFn: () => vincular_correo_iafas(correo_id, cuenta?.identificacion_interna ?? ""),
    onSuccess: al_terminar,
  });
  return (
    <>
      <div className={estilos.fila_resolver}>
        <BuscadorCuenta
          iafas_codigo={codigo_iafas ?? undefined}
          elegida={cuenta}
          al_elegir={set_cuenta}
        />
        <Boton
          variante="primario"
          onClick={() => vinculacion.mutate()}
          disabled={vinculacion.isPending || cuenta === null}
        >
          Vincular a la cuenta
        </Boton>
      </div>
      <MensajeErrorMutacion error={vinculacion.error} texto_por_defecto="No se pudo vincular." />
    </>
  );
}

function DescartarCorreo({ correo_id, al_terminar }: PropiedadesResolver) {
  const [motivo, set_motivo] = useState("");
  const descarte = useMutation({
    mutationFn: () => descartar_correo_iafas(correo_id, motivo.trim()),
    onSuccess: al_terminar,
  });
  return (
    <>
      <div className={estilos.fila_resolver}>
        <CampoTexto
          etiqueta="Motivo del descarte"
          value={motivo}
          maxLength={300}
          onChange={(evento) => set_motivo(evento.target.value)}
        />
        <Boton
          variante="secundario"
          onClick={() => descarte.mutate()}
          disabled={descarte.isPending || motivo.trim().length < 5}
        >
          Descartar
        </Boton>
      </div>
      <MensajeErrorMutacion error={descarte.error} texto_por_defecto="No se pudo descartar." />
    </>
  );
}

function ResolverCorreo({
  correo_id,
  codigo_iafas,
  al_cerrar,
}: {
  correo_id: number;
  codigo_iafas: string | null;
  al_cerrar: () => void;
}) {
  const cliente = useQueryClient();
  const al_terminar = async () => {
    await cliente.invalidateQueries();
    al_cerrar();
  };
  return (
    <div className={estilos.resolver}>
      <VincularCorreo correo_id={correo_id} codigo_iafas={codigo_iafas} al_terminar={al_terminar} />
      <DescartarCorreo correo_id={correo_id} al_terminar={al_terminar} />
    </div>
  );
}

interface Propiedades {
  correo_id: number;
  al_cerrar: () => void;
}

export function DialogoCorreo({ correo_id, al_cerrar }: Propiedades) {
  const { sesion } = usar_sesion();
  const consulta = useQuery({
    queryKey: ["correos_iafas", "detalle", correo_id],
    queryFn: () => consultar_correo_iafas(correo_id),
  });
  const correo = consulta.data;
  const puede_revisar = sesion?.roles.some((rol) => _REVISA.includes(rol)) ?? false;

  return (
    <Dialogo
      titulo="Correo recibido"
      ancho="grande"
      al_cerrar={al_cerrar}
      acciones={
        <Boton variante="secundario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      {consulta.isError ? <Mensaje tipo="error" texto="No se pudo obtener el correo." /> : null}
      {correo ? <ContenidoCorreo correo={correo} /> : null}
      {correo && correo.estado === "POR_REVISAR" && puede_revisar ? (
        <ResolverCorreo
          correo_id={correo_id}
          codigo_iafas={correo.codigo_iafas ?? null}
          al_cerrar={al_cerrar}
        />
      ) : null}
    </Dialogo>
  );
}
