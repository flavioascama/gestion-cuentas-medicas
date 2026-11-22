import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { actualizar_remitente_iafas, type ParametrosIafas } from "../../api/parametros";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import estilos from "./administracion.module.css";

// Remitente del que se aceptan comunicaciones por correo de cada
// aseguradora (2026-11-15). Un correo de otro remitente no se aplica solo:
// queda por revisar.

function DialogoRemitente({ iafas, al_cerrar }: { iafas: ParametrosIafas; al_cerrar: () => void }) {
  const cliente_consultas = useQueryClient();
  const [remitente, set_remitente] = useState(iafas.correo_remitente ?? "");
  const mutacion = useMutation({
    mutationFn: () => actualizar_remitente_iafas(iafas.iafas_id, remitente.trim() || null),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["administracion", "parametros"] });
      al_cerrar();
    },
  });

  return (
    <Dialogo
      titulo={`Correo de ${iafas.razon_social}`}
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={mutacion.isPending}
          >
            Guardar
          </Boton>
        </>
      }
    >
      <CampoTexto
        etiqueta="Remitentes autorizados (separados por coma)"
        value={remitente}
        maxLength={200}
        placeholder="auditoria@iafas.pe o @iafas.pe"
        onChange={(evento) => set_remitente(evento.target.value)}
      />
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo guardar." />
    </Dialogo>
  );
}

function columnas(al_editar: (fila: ParametrosIafas) => void): ColumnaTabla<ParametrosIafas>[] {
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
    {
      clave: "correo_remitente",
      encabezado: "Remitente autorizado",
      formatear: (fila) => fila.correo_remitente ?? "Sin registrar",
    },
    {
      clave: "iafas_id",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_editar(fila)}>
          Editar
        </Boton>
      ),
    },
  ];
}

interface Propiedades {
  filas: ParametrosIafas[];
  cargando: boolean;
  error: unknown;
}

export function SeccionRemitentes({ filas, cargando, error }: Propiedades) {
  const [editando, set_editando] = useState<ParametrosIafas | null>(null);

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Correo de comunicaciones</div>
      <TablaDatos
        columnas={columnas(set_editando)}
        filas={filas}
        obtener_clave={(fila) => fila.iafas_id}
        cargando={cargando}
        error={error}
        mensaje_vacio="No hay IAFAS registradas."
      />
      {editando ? <DialogoRemitente iafas={editando} al_cerrar={() => set_editando(null)} /> : null}
    </div>
  );
}
