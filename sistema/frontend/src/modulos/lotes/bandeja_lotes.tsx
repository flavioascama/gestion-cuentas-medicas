import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listar_iafas, type ResumenIafas } from "../../api/iafas";
import { solicitar_envio_susalud, type ResumenLote } from "../../api/lotes";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { IconoFlechaDerecha } from "../../componentes_base/iconos_tabla";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Mensaje } from "../../componentes_base/mensaje";
import { Paginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { ProgresoTrabajo } from "../../componentes_base/progreso_trabajo";
import { Selector } from "../../componentes_base/selector";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import { DialogoGenerarLote } from "./dialogo_generar_lote";
import { usar_bandeja_lotes } from "./usar_lotes";
import { ControlSusalud } from "./control_susalud";
import estilos from "./bandeja_lotes.module.css";

// El nombre de la IAFAS (no solo su codigo numerico) se resuelve con el
// mismo listado que ya trae el desplegable de filtro -- sin pedirselo
// de nuevo al backend, que hoy solo devuelve el codigo en /lotes
// (ResumenLoteRespuesta). Antes de esto, la columna mostraba el codigo
// crudo mientras Cuentas ya mostraba el nombre completo de la
// aseguradora: inconsistencia real entre las dos bandejas.
function usar_mapa_iafas(): Map<string, string> {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });
  return new Map((consulta_iafas.data ?? []).map((i) => [i.codigo, i.razon_social]));
}

function construir_columnas(mapa_iafas: Map<string, string>): ColumnaTabla<ResumenLote>[] {
  return [
    {
      clave: "numero",
      encabezado: "N.° de lote",
      formatear: (fila) => (
        <span className={estilos.enlace_lote}>
          {fila.numero}
          <IconoFlechaDerecha />
        </span>
      ),
    },
    { clave: "periodo", encabezado: "Periodo" },
    {
      clave: "iafas_codigo",
      encabezado: "IAFAS",
      formatear: (fila) => mapa_iafas.get(fila.iafas_codigo) ?? fila.iafas_codigo,
    },
    {
      clave: "estado",
      encabezado: "Estado",
      formatear: (fila) => (
        <span className={estilos.estados}>
          <EtiquetaEstado estado={fila.estado} />
          {fila.monitoreo_excedido ? <EtiquetaEstado estado="EXCEDIDO" /> : null}
        </span>
      ),
    },
    {
      clave: "cantidad_documentos",
      encabezado: "Cuentas",
      alinear_centro: true,
    },
    {
      clave: "monto_total",
      encabezado: "Monto",
      alinear_derecha: true,
      formatear: (fila) => formatear_monto(fila.monto_total),
    },
    {
      clave: "generado_en",
      encabezado: "Generado",
      formatear: (fila) => formatear_fecha_hora(fila.generado_en),
    },
  ];
}

const _OPCIONES_ESTADO = [
  { valor: "", etiqueta: "Todos" },
  { valor: "GENERADO", etiqueta: "Generado" },
  { valor: "CARGADO_VALIDADOR", etiqueta: "Cargado en el validador" },
  { valor: "OBSERVADO_VALIDADOR", etiqueta: "Observado por el validador" },
  { valor: "VALIDADO", etiqueta: "Validado" },
  { valor: "REMITIDO_IAFAS", etiqueta: "Remitido a la IAFAS" },
  { valor: "ACEPTADO", etiqueta: "Aceptado" },
  { valor: "RECHAZADO", etiqueta: "Rechazado" },
];

interface Filtros {
  periodo: string;
  estado: string;
  iafas_id: string;
}

function construir_opciones_iafas(iafas: ResumenIafas[]): { valor: string; etiqueta: string }[] {
  return [
    { valor: "", etiqueta: "Todas" },
    ...iafas.map((i) => ({ valor: String(i.id), etiqueta: `${i.codigo} — ${i.razon_social}` })),
  ];
}

// AAAAMM (formato que ya entiende el backend) <-> AAAA-MM (formato que
// exige <input type="month">): la misma conversion sirve para mostrar
// el periodo de forma legible en el boton de SUSALUD.
function formatear_periodo_legible(periodo: string): string {
  if (periodo.length !== 6) return "";
  return `${periodo.slice(0, 4)}-${periodo.slice(4, 6)}`;
}

function periodo_desde_mes_input(valor: string): string {
  return valor.replace("-", "");
}

function FiltroPeriodo({
  periodo,
  al_cambiar,
}: {
  periodo: string;
  al_cambiar: (periodo: string) => void;
}) {
  return (
    <div className={estilos.filtro}>
      <CampoTexto
        etiqueta="Periodo"
        type="month"
        placeholder="Todos los periodos"
        value={formatear_periodo_legible(periodo)}
        onChange={(evento) => al_cambiar(periodo_desde_mes_input(evento.target.value))}
      />
    </div>
  );
}

function FiltrosBandejaLotes({
  filtros,
  al_cambiar,
  busqueda,
  al_cambiar_busqueda,
}: {
  filtros: Filtros;
  al_cambiar: (filtros: Filtros) => void;
  busqueda: string;
  al_cambiar_busqueda: (busqueda: string) => void;
}) {
  const consulta_iafas = useQuery({ queryKey: ["iafas"], queryFn: listar_iafas });

  return (
    <div className={estilos.filtros}>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => al_cambiar_busqueda(evento.target.value)}
          placeholder="N.° de lote"
        />
      </div>
      <FiltroPeriodo
        periodo={filtros.periodo}
        al_cambiar={(periodo) => al_cambiar({ ...filtros, periodo })}
      />
      <div className={estilos.filtro}>
        <Selector
          etiqueta="Estado"
          opciones={_OPCIONES_ESTADO}
          value={filtros.estado}
          onChange={(evento) => al_cambiar({ ...filtros, estado: evento.target.value })}
        />
      </div>
      <div className={estilos.filtro}>
        <Selector
          etiqueta="IAFAS"
          opciones={construir_opciones_iafas(consulta_iafas.data ?? [])}
          value={filtros.iafas_id}
          onChange={(evento) => al_cambiar({ ...filtros, iafas_id: evento.target.value })}
        />
      </div>
    </div>
  );
}

function AccionEnvioSusalud({ periodo }: { periodo: string }) {
  const { sesion } = usar_sesion();
  const cliente_consultas = useQueryClient();
  const [trabajo_id, set_trabajo_id] = useState<number | null>(null);

  const mutacion = useMutation({
    mutationFn: () => solicitar_envio_susalud(periodo),
    onSuccess: (respuesta) => set_trabajo_id(respuesta.trabajo_id),
  });

  if (!sesion?.roles.includes("analista") || !periodo) return null;

  return (
    <div className={estilos.envio_susalud}>
      <Boton
        variante="secundario"
        onClick={() => mutacion.mutate()}
        disabled={mutacion.isPending || trabajo_id !== null}
      >
        Enviar periodo {formatear_periodo_legible(periodo)} a SUSALUD
      </Boton>
      {trabajo_id !== null ? (
        <ProgresoTrabajo
          trabajo_id={trabajo_id}
          al_completar={() => void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] })}
        />
      ) : null}
      {mutacion.isSuccess && mutacion.data.trabajo_id === null ? (
        <Mensaje
          tipo="advertencia"
          texto="No hay lotes validados pendientes de envío en ese periodo."
        />
      ) : null}
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo encolar el envío."
      />
    </div>
  );
}

function AccionGenerarLote({ al_generar }: { al_generar: (lote_id: number) => void }) {
  const { sesion } = usar_sesion();
  const cliente_consultas = useQueryClient();
  const [mostrar_dialogo, set_mostrar_dialogo] = useState(false);

  if (!sesion?.roles.includes("analista")) return null;

  return (
    <>
      <Boton variante="primario" onClick={() => set_mostrar_dialogo(true)}>
        Generar lote
      </Boton>
      {mostrar_dialogo ? (
        <DialogoGenerarLote
          al_cerrar={() => set_mostrar_dialogo(false)}
          al_generar_conforme={(lote_id) => {
            set_mostrar_dialogo(false);
            void cliente_consultas.invalidateQueries({ queryKey: ["lotes"] });
            al_generar(lote_id);
          }}
        />
      ) : null}
    </>
  );
}

// Busqueda de texto libre, del lado del cliente: se aplica sobre el
// resultado que el servidor ya filtro por periodo/estado/IAFAS.
function coincide_busqueda_lote(fila: ResumenLote, busqueda: string): boolean {
  if (!busqueda) return true;
  return fila.numero.toLowerCase().includes(busqueda.toLowerCase());
}

// Separado de BandejaLotes (que si no pasa el limite de lineas del
// linter): el unico manejador de filtros que esa funcion necesitaba.
function construir_manejador_filtros(
  set_filtros: Dispatch<SetStateAction<Filtros>>,
  set_pagina: (pagina: number) => void,
) {
  return (nuevos: Filtros) => {
    set_filtros(nuevos);
    set_pagina(1);
  };
}

function EncabezadoLotes({
  filtros,
  al_cambiar_filtros,
  busqueda,
  al_cambiar_busqueda,
  al_generar,
}: {
  filtros: Filtros;
  al_cambiar_filtros: (filtros: Filtros) => void;
  busqueda: string;
  al_cambiar_busqueda: (busqueda: string) => void;
  al_generar: (lote_id: number) => void;
}) {
  return (
    <>
      <TituloPagina
        titulo="Lotes de facturación"
        acciones={<AccionGenerarLote al_generar={al_generar} />}
      />
      <div className={estilos.tarjeta_filtros}>
        <FiltrosBandejaLotes
          filtros={filtros}
          al_cambiar={al_cambiar_filtros}
          busqueda={busqueda}
          al_cambiar_busqueda={al_cambiar_busqueda}
        />
      </div>
    </>
  );
}

export function BandejaLotes() {
  const navegar = useNavigate();
  const [filtros, set_filtros] = useState<Filtros>({ periodo: "", estado: "", iafas_id: "" });
  const [busqueda, set_busqueda] = useState("");
  const consulta = usar_bandeja_lotes({
    periodo: filtros.periodo || undefined,
    estado: filtros.estado || undefined,
    iafas_id: filtros.iafas_id ? Number(filtros.iafas_id) : undefined,
  });
  const mapa_iafas = usar_mapa_iafas();

  const filtrados = (consulta.data ?? []).filter((fila) => coincide_busqueda_lote(fila, busqueda));
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filtrados);
  const al_cambiar_filtros = construir_manejador_filtros(set_filtros, set_pagina);

  return (
    <div className={estilos.panel}>
      <EncabezadoLotes
        filtros={filtros}
        al_cambiar_filtros={al_cambiar_filtros}
        busqueda={busqueda}
        al_cambiar_busqueda={(valor) => {
          set_busqueda(valor);
          set_pagina(1);
        }}
        al_generar={(lote_id) => void navegar(`/lotes/${lote_id}`)}
      />
      <AccionEnvioSusalud periodo={filtros.periodo} />
      <TablaDatos
        columnas={construir_columnas(mapa_iafas)}
        filas={filas_pagina}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay lotes para los filtros seleccionados."
        al_hacer_clic_fila={(fila) => void navegar(`/lotes/${fila.id}`)}
      />
      <Paginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filtrados.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="lotes"
      />
      <ControlSusalud />
    </div>
  );
}
