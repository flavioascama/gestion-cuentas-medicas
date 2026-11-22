import { useRef } from "react";
import type { ResumenAtencion } from "../../api/atenciones";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha } from "../../utilidades/formato";
import { etiqueta_tipo_atencion } from "./etiquetas_atencion";
import { usar_importar_atencion } from "./usar_importar_atencion";

function construir_columnas(
  nombre_iafas: (codigo: string) => string,
  importando: boolean,
  al_importar: (atencion_id: string) => void,
): ColumnaTabla<ResumenAtencion>[] {
  return [
    { clave: "atencion_id", encabezado: "Código" },
    {
      clave: "fecha_prestacion",
      encabezado: "Fecha",
      formatear: (fila) => formatear_fecha(fila.fecha_prestacion),
    },
    {
      clave: "tipo_atencion",
      encabezado: "Tipo",
      formatear: (fila) => etiqueta_tipo_atencion(fila.tipo_atencion),
    },
    {
      clave: "paciente",
      encabezado: "Paciente",
      formatear: (fila) => `${fila.paciente.nombres} ${fila.paciente.apellidos}`,
    },
    {
      clave: "paciente",
      encabezado: "Documento",
      formatear: (fila) => fila.paciente.numero_documento,
    },
    {
      clave: "iafas_codigo",
      encabezado: "IAFAS",
      formatear: (fila) => nombre_iafas(fila.iafas_codigo),
    },
    {
      clave: "atencion_id",
      encabezado: "",
      formatear: (fila) => (
        <Boton disabled={importando} onClick={() => al_importar(fila.atencion_id)}>
          Importar
        </Boton>
      ),
    },
  ];
}

function BotonCargarArchivo({
  deshabilitado,
  al_elegir,
}: {
  deshabilitado: boolean;
  al_elegir: (archivo: File) => void;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={entrada}
        type="file"
        accept=".json,application/json"
        hidden
        onChange={(evento) => {
          const archivo = evento.target.files?.[0];
          evento.target.value = "";
          if (archivo) al_elegir(archivo);
        }}
      />
      <Boton disabled={deshabilitado} onClick={() => entrada.current?.click()}>
        Cargar archivo de la atención
      </Boton>
    </>
  );
}

function ContenidoImportar({
  importacion,
}: {
  importacion: ReturnType<typeof usar_importar_atencion>;
}) {
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(
    importacion.filas,
  );
  const { mutacion } = importacion;
  const columnas = construir_columnas(importacion.nombre_iafas, mutacion.isPending, (atencion_id) =>
    mutacion.mutate({ atencion_id }),
  );
  return (
    <>
      <CampoTexto
        etiqueta="Buscar"
        value={importacion.busqueda}
        onChange={(evento) => {
          importacion.set_busqueda(evento.target.value);
          set_pagina(1);
        }}
        placeholder="Documento o nombre"
      />
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo importar." />
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={importacion.filas.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="atenciones"
      >
        <TablaDatos
          columnas={columnas}
          filas={filas_pagina}
          obtener_clave={(fila) => fila.atencion_id}
          cargando={importacion.atenciones.isPending}
          error={importacion.atenciones.error}
          mensaje_vacio="No hay atenciones por importar."
        />
      </ConPaginacion>
    </>
  );
}

export function DialogoImportarAtencion({
  al_cerrar,
  al_importar,
}: {
  al_cerrar: () => void;
  al_importar: (cuenta_id: number) => void;
}) {
  const importacion = usar_importar_atencion(al_importar);
  const { mutacion } = importacion;
  return (
    <Dialogo
      titulo="Importar atención"
      al_cerrar={al_cerrar}
      ancho="grande"
      acciones={
        <>
          <BotonCargarArchivo
            deshabilitado={mutacion.isPending}
            al_elegir={(archivo) => mutacion.mutate({ archivo })}
          />
          <Boton onClick={al_cerrar}>Cerrar</Boton>
        </>
      }
    >
      <ContenidoImportar importacion={importacion} />
    </Dialogo>
  );
}
