import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  corregir_cuenta_rechazada,
  obtener_rechazo_cuenta,
  type RechazoCuenta,
} from "../../api/reenvio";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "./aviso_rechazo_cuenta.module.css";

// T-05 (Tabla 58, camino de excepcion del TO-BE): una cuenta rechazada
// por la IAFAS muestra por que, y el analista la corrige para incluirla
// en un lote nuevo. Antes de la verificacion de cumplimiento del 12 de
// noviembre no habia ninguna salida de RECHAZADA salvo la anulacion.

interface PropiedadesDialogo {
  cuenta_id: number;
  al_cerrar: () => void;
}

function DialogoCorreccionReenvio({ cuenta_id, al_cerrar }: PropiedadesDialogo) {
  const cliente_consultas = useQueryClient();
  const [descripcion, set_descripcion] = useState("");

  const mutacion = useMutation({
    mutationFn: () => corregir_cuenta_rechazada(cuenta_id, descripcion.trim()),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas"] });
      al_cerrar();
    },
  });

  return (
    <Dialogo
      titulo="Corregir la cuenta para su reenvío"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending || !descripcion.trim()}
          >
            Habilitar reenvío
          </Boton>
        </>
      }
    >
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo corregir." />
      <CampoTexto
        etiqueta="Corrección realizada"
        value={descripcion}
        onChange={(evento) => set_descripcion(evento.target.value)}
      />
    </Dialogo>
  );
}

function DetalleRechazo({ rechazo, cargando }: { rechazo?: RechazoCuenta; cargando: boolean }) {
  if (!rechazo) {
    return (
      <p className={estilos.detalle}>
        {cargando ? "Cargando el motivo del rechazo…" : "Sin detalle del rechazo."}
      </p>
    );
  }
  return (
    <>
      <p className={estilos.detalle}>
        Lote{" "}
        <Link to={`/lotes/${rechazo.lote_id}`} className={estilos.enlace}>
          {rechazo.numero_lote}
        </Link>
        {rechazo.rechazado_en ? ` · ${formatear_fecha_hora(rechazo.rechazado_en)}` : null}
      </p>
      <p className={estilos.motivo}>
        <span className={estilos.etiqueta}>Motivo:</span>{" "}
        {rechazo.motivo ?? "La IAFAS no informó un motivo."}
      </p>
    </>
  );
}

export function AvisoRechazoCuenta({ cuenta_id, estado }: { cuenta_id: number; estado: string }) {
  const { sesion } = usar_sesion();
  const [mostrar_dialogo, set_mostrar_dialogo] = useState(false);
  const rechazada = estado === "RECHAZADA";
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "rechazo"],
    queryFn: () => obtener_rechazo_cuenta(cuenta_id),
    enabled: rechazada,
    retry: false,
  });

  if (!rechazada) return null;

  return (
    <section className={estilos.aviso} aria-labelledby="titulo_aviso_rechazo">
      <div className={estilos.contenido}>
        <h2 id="titulo_aviso_rechazo" className={estilos.titulo}>
          Rechazada por la IAFAS
        </h2>
        <DetalleRechazo rechazo={consulta.data} cargando={consulta.isPending} />
      </div>
      {sesion?.roles.includes("analista") ? (
        <Boton variante="primario" onClick={() => set_mostrar_dialogo(true)}>
          Corregir y habilitar reenvío
        </Boton>
      ) : null}
      {mostrar_dialogo ? (
        <DialogoCorreccionReenvio
          cuenta_id={cuenta_id}
          al_cerrar={() => set_mostrar_dialogo(false)}
        />
      ) : null}
    </section>
  );
}
