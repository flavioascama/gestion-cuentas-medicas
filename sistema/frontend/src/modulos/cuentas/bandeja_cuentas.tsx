import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { Boton } from "../../componentes_base/boton";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { IconoFlechaDerecha } from "../../componentes_base/iconos_tabla";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import type { ResumenCuenta } from "../../api/cuentas";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_estado_de_sesion } from "../../utilidades/estado_de_sesion";
import { formatear_fecha } from "../../utilidades/formato";
import { DialogoNuevaCuenta } from "./dialogo_nueva_cuenta";
import { FiltrosBandejaCuentas, type FiltrosCuentas } from "./filtros_bandeja_cuentas";
import { usar_bandeja_cuentas, usar_vencimientos } from "./usar_cuentas";
import type { Vencimiento } from "../../api/plazos";
import { PlazoCuenta } from "./plazo_cuenta";
import estilos from "./bandeja_cuentas.module.css";

function construir_columnas(vencimientos: Map<number, Vencimiento>): ColumnaTabla<ResumenCuenta>[] {
  return [
    {
      clave: "identificacion_interna",
      encabezado: "Identificación",
      // Mismo enlace que el numero de lote: se ve que la fila se abre.
      formatear: (fila) => (
        <span className={estilos.enlace_cuenta}>
          {fila.identificacion_interna}
          <IconoFlechaDerecha />
        </span>
      ),
    },
    {
      clave: "estado",
      encabezado: "Estado",
      formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
    },
    {
      clave: "id",
      encabezado: "Vence",
      formatear: (fila) => <PlazoCuenta vencimiento={vencimientos.get(fila.id)} />,
    },
    {
      clave: "fecha_prestacion",
      encabezado: "Fecha de prestación",
      formatear: (fila) => formatear_fecha(fila.fecha_prestacion),
    },
    {
      clave: "nombres_asegurado",
      encabezado: "Asegurado",
      formatear: (fila) => `${fila.nombres_asegurado} ${fila.apellidos_asegurado}`,
    },
    { clave: "iafas_razon_social", encabezado: "IAFAS" },
  ];
}

const _FILTROS_INICIALES: FiltrosCuentas = { etapa: "", estado: "", iafas_codigo: "", fecha: "" };

// El panel gerencial abre esta bandeja ya filtrada (?estado=&iafas=).
function filtros_desde_url(parametros: URLSearchParams): FiltrosCuentas {
  return {
    ..._FILTROS_INICIALES,
    etapa: parametros.get("etapa") ?? "",
    estado: parametros.get("estado") ?? "",
    iafas_codigo: parametros.get("iafas") ?? "",
  };
}

// Busqueda de texto libre, del lado del cliente: se aplica sobre el
// resultado que el servidor ya filtro por estado/IAFAS/fecha, no es un
// cuarto filtro enviado al API.
function coincide_busqueda(fila: ResumenCuenta, busqueda: string): boolean {
  if (!busqueda) return true;
  const objetivo = busqueda.toLowerCase();
  const asegurado = `${fila.nombres_asegurado} ${fila.apellidos_asegurado}`.toLowerCase();
  return (
    fila.identificacion_interna.toLowerCase().includes(objetivo) || asegurado.includes(objetivo)
  );
}

// Un solo punto donde se arman los tres manejadores de los filtros, en
// vez de declararlos sueltos en el cuerpo de BandejaCuentas -- ahi
// hacian que la funcion pasara el limite de lineas del linter.
function construir_manejadores_filtros(
  set_filtros: (filtros: FiltrosCuentas) => void,
  set_busqueda: (busqueda: string) => void,
  set_pagina: (pagina: number) => void,
) {
  return {
    al_cambiar_filtros: (nuevos: FiltrosCuentas) => {
      set_filtros(nuevos);
      set_pagina(1);
    },
    al_cambiar_busqueda: (valor: string) => {
      set_busqueda(valor);
      set_pagina(1);
    },
    al_limpiar_filtros: () => {
      set_filtros(_FILTROS_INICIALES);
      set_busqueda("");
      set_pagina(1);
    },
  };
}

function AccionNuevaCuenta({ al_crear }: { al_crear: (cuenta_id: number) => void }) {
  const { sesion } = usar_sesion();
  const cliente_consultas = useQueryClient();
  const [mostrar_dialogo, set_mostrar_dialogo] = useState(false);

  if (!sesion?.roles.includes("analista")) return null;

  return (
    <>
      <Boton variante="primario" onClick={() => set_mostrar_dialogo(true)}>
        Nueva cuenta
      </Boton>
      {mostrar_dialogo ? (
        <DialogoNuevaCuenta
          al_cerrar={() => set_mostrar_dialogo(false)}
          al_registrar={(cuenta_id) => {
            set_mostrar_dialogo(false);
            void cliente_consultas.invalidateQueries({ queryKey: ["cuentas"] });
            al_crear(cuenta_id);
          }}
        />
      ) : null}
    </>
  );
}

function EncabezadoCuentas({
  filtros,
  al_cambiar_filtros,
  busqueda,
  al_cambiar_busqueda,
  al_limpiar_filtros,
  al_crear,
}: {
  filtros: FiltrosCuentas;
  al_cambiar_filtros: (filtros: FiltrosCuentas) => void;
  busqueda: string;
  al_cambiar_busqueda: (busqueda: string) => void;
  al_limpiar_filtros: () => void;
  al_crear: (cuenta_id: number) => void;
}) {
  return (
    <>
      <TituloPagina titulo="Cuentas médicas" acciones={<AccionNuevaCuenta al_crear={al_crear} />} />
      <div className={estilos.tarjeta_filtros}>
        <FiltrosBandejaCuentas
          filtros={filtros}
          al_cambiar={al_cambiar_filtros}
          busqueda={busqueda}
          al_cambiar_busqueda={al_cambiar_busqueda}
          al_limpiar={al_limpiar_filtros}
        />
      </div>
    </>
  );
}

// Un enlace con filtros en la direccion manda; si no, se conservan los de
// la sesion: al abrir una cuenta y volver, la bandeja queda igual.
function usar_filtros_cuentas() {
  const [parametros] = useSearchParams();
  const de_url = parametros.toString() ? filtros_desde_url(parametros) : null;
  const [filtros, set_filtros] = usar_estado_de_sesion(
    "cuentas.filtros",
    _FILTROS_INICIALES,
    de_url,
  );
  const [busqueda, set_busqueda] = usar_estado_de_sesion(
    "cuentas.busqueda",
    "",
    de_url ? "" : null,
  );
  return { filtros, set_filtros, busqueda, set_busqueda };
}

export function BandejaCuentas() {
  const navegar = useNavigate();
  const { filtros, set_filtros, busqueda, set_busqueda } = usar_filtros_cuentas();
  const consulta = usar_bandeja_cuentas({
    estado: filtros.estado || undefined,
    etapa: filtros.etapa || undefined,
    iafas_codigo: filtros.iafas_codigo || undefined,
    fecha_prestacion: filtros.fecha || undefined,
  });

  const filtradas = (consulta.data ?? []).filter((fila) => coincide_busqueda(fila, busqueda));
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filtradas);
  const vencimientos = usar_vencimientos();
  const columnas = construir_columnas(vencimientos);
  const manejadores = construir_manejadores_filtros(set_filtros, set_busqueda, set_pagina);

  return (
    <div className={estilos.panel}>
      <EncabezadoCuentas
        filtros={filtros}
        al_cambiar_filtros={manejadores.al_cambiar_filtros}
        busqueda={busqueda}
        al_cambiar_busqueda={manejadores.al_cambiar_busqueda}
        al_limpiar_filtros={manejadores.al_limpiar_filtros}
        al_crear={(cuenta_id) => void navegar(`/cuentas/${cuenta_id}`)}
      />
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filtradas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="cuentas"
      >
        <TablaDatos
          columnas={columnas}
          filas={filas_pagina}
          obtener_clave={(fila) => fila.id}
          cargando={consulta.isPending}
          actualizando={consulta.isPlaceholderData}
          error={consulta.error}
          mensaje_vacio="No hay cuentas para los filtros seleccionados."
          al_hacer_clic_fila={(fila) => void navegar(`/cuentas/${fila.id}`)}
        />
      </ConPaginacion>
    </div>
  );
}
