import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  listar_registros_contingencia,
  revisar_registro_contingencia,
  type RegistroContingencia,
} from "../../api/contingencia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { ControlSegmentado } from "../../componentes_base/control_segmentado";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { formatear_fecha_hora } from "../../utilidades/formato";
import estilos from "./contingencia.module.css";

// C-18: "cada resultado registrado en modo de contingencia... se somete a
// la revision posterior del jefe de cuentas medicas".

const _ETIQUETA_REVISION: Record<string, string> = {
  PENDIENTE: "Pendiente",
  CONFORME: "Conforme",
  NO_CONFORME: "No conforme",
};

function Referencia({ fila }: { fila: RegistroContingencia }) {
  if (fila.cuenta_medica_id) {
    return (
      <Link to={`/cuentas/${fila.cuenta_medica_id}`} className={estilos.enlace}>
        {fila.identificacion_interna ?? `Cuenta ${fila.cuenta_medica_id}`}
      </Link>
    );
  }
  return (
    <Link to={`/lotes/${fila.lote_id ?? ""}`} className={estilos.enlace}>
      Lote {fila.numero_lote ?? fila.lote_id}
    </Link>
  );
}

function construir_columnas(al_revisar: (fila: RegistroContingencia) => void) {
  const columnas: ColumnaTabla<RegistroContingencia>[] = [
    {
      clave: "registrado_en",
      encabezado: "Registrado",
      formatear: (f) => formatear_fecha_hora(f.registrado_en),
    },
    {
      clave: "tipo_operacion",
      encabezado: "Operación",
      formatear: (f) => (f.tipo_operacion === "COBERTURA" ? "Cobertura" : "Validación del lote"),
    },
    {
      clave: "cuenta_medica_id",
      encabezado: "Cuenta o lote",
      formatear: (f) => <Referencia fila={f} />,
    },
    { clave: "resumen", encabezado: "Resultado registrado" },
    { clave: "sustento", encabezado: "Sustento" },
    { clave: "registrado_por", encabezado: "Analista" },
    {
      clave: "estado_revision",
      encabezado: "Revisión",
      formatear: (f) => (
        <span className={`${estilos.revision} ${estilos[f.estado_revision] ?? ""}`}>
          {_ETIQUETA_REVISION[f.estado_revision] ?? f.estado_revision}
        </span>
      ),
    },
    {
      clave: "evento_id",
      encabezado: "Acciones",
      alinear_centro: true,
      formatear: (f) =>
        f.estado_revision === "PENDIENTE" ? (
          <Boton variante="secundario" onClick={() => al_revisar(f)}>
            Revisar
          </Boton>
        ) : (
          (f.revisado_por ?? "—")
        ),
    },
  ];
  return columnas;
}

// "No conforme" exige un comentario: el jefe deja dicho que falto.
function AccionesRevision({
  ocupado,
  sin_comentario,
  al_resolver,
}: {
  ocupado: boolean;
  sin_comentario: boolean;
  al_resolver: (conforme: boolean) => void;
}) {
  return (
    <>
      <Boton
        variante="destructivo"
        onClick={() => al_resolver(false)}
        disabled={ocupado || sin_comentario}
      >
        No conforme
      </Boton>
      <Boton variante="primario" onClick={() => al_resolver(true)} disabled={ocupado}>
        Conforme
      </Boton>
    </>
  );
}

function DialogoRevision({
  registro,
  al_cerrar,
}: {
  registro: RegistroContingencia;
  al_cerrar: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [comentario, set_comentario] = useState("");
  const mutacion = useMutation({
    mutationFn: (conforme: boolean) =>
      revisar_registro_contingencia(registro.evento_id, conforme, comentario),
    onSuccess: () => {
      void cliente_consultas.invalidateQueries({ queryKey: ["contingencias"] });
      al_cerrar();
    },
  });
  return (
    <Dialogo
      titulo="Revisar el registro en contingencia"
      al_cerrar={al_cerrar}
      acciones={
        <AccionesRevision
          ocupado={mutacion.isPending}
          sin_comentario={!comentario.trim()}
          al_resolver={(conforme) => mutacion.mutate(conforme)}
        />
      }
    >
      <p className={estilos.nota}>
        {registro.resumen}. Sustento: {registro.sustento}
      </p>
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar la revisión."
      />
      <CampoTexto
        etiqueta="Comentario (obligatorio si no es conforme)"
        value={comentario}
        onChange={(evento) => set_comentario(evento.target.value)}
      />
    </Dialogo>
  );
}

function EncabezadoContingencias() {
  return (
    <>
      <TituloPagina titulo="Registros en contingencia" />
    </>
  );
}

export function BandejaContingencias() {
  const [solo_pendientes, set_solo_pendientes] = useState("pendientes");
  const [en_revision, set_en_revision] = useState<RegistroContingencia | null>(null);
  const consulta = useQuery({
    queryKey: ["contingencias"],
    queryFn: listar_registros_contingencia,
  });
  const todos = consulta.data ?? [];
  const filas =
    solo_pendientes === "pendientes"
      ? todos.filter((r) => r.estado_revision === "PENDIENTE")
      : todos;
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filas);

  return (
    <div>
      <EncabezadoContingencias />
      <div className={estilos.filtros}>
        <ControlSegmentado
          opciones={[
            { valor: "pendientes", etiqueta: "Pendientes" },
            { valor: "todos", etiqueta: "Todos" },
          ]}
          valor={solo_pendientes}
          al_cambiar={set_solo_pendientes}
          etiqueta_accesible="Filtrar por revisión"
        />
      </div>
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="registros"
      >
        <TablaDatos
          columnas={construir_columnas(set_en_revision)}
          filas={filas_pagina}
          obtener_clave={(fila) => fila.evento_id}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="No hay registros en contingencia por revisar."
        />
      </ConPaginacion>
      {en_revision ? (
        <DialogoRevision registro={en_revision} al_cerrar={() => set_en_revision(null)} />
      ) : null}
    </div>
  );
}
