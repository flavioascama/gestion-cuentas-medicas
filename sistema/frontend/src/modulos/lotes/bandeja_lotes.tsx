import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listar_iafas } from "../../api/iafas";
import type { ResumenLote } from "../../api/lotes";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { IconoLotes } from "../../componentes_base/iconos_navegacion";
import { IconoFlechaDerecha } from "../../componentes_base/iconos_tabla";
import { Paginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { Pestanas, type DefinicionPestana } from "../../componentes_base/pestanas";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_estado_de_sesion } from "../../utilidades/estado_de_sesion";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";
import { AccionEnvioSusalud } from "./accion_envio_susalud";
import { ControlSusalud } from "./control_susalud";
import { DialogoGenerarLote } from "./dialogo_generar_lote";
import { FiltrosBandejaLotes } from "./filtros_bandeja_lotes";
import { FILTROS_VACIOS, type Filtros } from "./filtros_lotes";
import { IconoCalendario } from "./iconos_detalle_lote";
import { usar_bandeja_lotes } from "./usar_lotes";
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

// Pestana "Lotes": filtros, envio del periodo elegido y la tabla de lotes.
function PanelLotes({ al_abrir_lote }: { al_abrir_lote: (lote_id: number) => void }) {
  // Se conservan al abrir un lote y volver a la bandeja.
  const [filtros, set_filtros] = usar_estado_de_sesion<Filtros>("lotes.filtros", FILTROS_VACIOS);
  const [busqueda, set_busqueda] = usar_estado_de_sesion("lotes.busqueda", "");
  const consulta = usar_bandeja_lotes({
    periodo: filtros.periodo || undefined,
    estado: filtros.estado || undefined,
    iafas_id: filtros.iafas_id ? Number(filtros.iafas_id) : undefined,
  });
  const mapa_iafas = usar_mapa_iafas();

  const filtrados = (consulta.data ?? []).filter((fila) => coincide_busqueda_lote(fila, busqueda));
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filtrados);
  const aplicar = (nuevos: Filtros, nueva_busqueda: string) => {
    set_filtros(nuevos);
    set_busqueda(nueva_busqueda);
    set_pagina(1);
  };

  return (
    <>
      <div className={estilos.tarjeta_filtros}>
        <FiltrosBandejaLotes
          filtros={filtros}
          al_cambiar={(nuevos) => aplicar(nuevos, busqueda)}
          busqueda={busqueda}
          al_cambiar_busqueda={(valor) => aplicar(filtros, valor)}
          al_limpiar={() => aplicar(FILTROS_VACIOS, "")}
        />
      </div>
      {/* La clave reinicia el progreso del envio al cambiar de periodo. */}
      <AccionEnvioSusalud key={filtros.periodo} periodo={filtros.periodo} />
      <TablaDatos
        columnas={construir_columnas(mapa_iafas)}
        filas={filas_pagina}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        actualizando={consulta.isPlaceholderData}
        error={consulta.error}
        mensaje_vacio="No hay lotes para los filtros seleccionados."
        al_hacer_clic_fila={(fila) => al_abrir_lote(fila.id)}
      />
      <Paginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filtrados.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="lotes"
      />
    </>
  );
}

export function BandejaLotes() {
  const navegar = useNavigate();
  const abrir_lote = (lote_id: number) => void navegar(`/lotes/${lote_id}`);
  // El reporte mensual tiene su propia pestana: antes quedaba debajo de
  // la tabla de lotes y se perdia al final de la pagina.
  const pestanas: DefinicionPestana[] = [
    {
      id: "lotes",
      etiqueta: "Lotes",
      icono: IconoLotes,
      contenido: <PanelLotes al_abrir_lote={abrir_lote} />,
    },
    {
      id: "reporte_susalud",
      etiqueta: "Reporte mensual a SUSALUD",
      icono: IconoCalendario,
      contenido: <ControlSusalud />,
    },
  ];

  return (
    <div className={estilos.panel}>
      <TituloPagina
        titulo="Lotes de facturación"
        acciones={<AccionGenerarLote al_generar={abrir_lote} />}
      />
      <Pestanas pestanas={pestanas} etiqueta_lista="Secciones de lotes de facturación" />
    </div>
  );
}
