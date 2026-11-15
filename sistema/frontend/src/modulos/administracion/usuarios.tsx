import { useState } from "react";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { etiquetas_roles } from "../../componentes_base/mapa_roles";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { DialogoUsuario } from "./dialogo_usuario";
import { usar_actualizar_usuario, usar_lista_usuarios } from "./usar_usuarios";
import estilos from "./administracion.module.css";

// CU-18: gestion de usuarios en su propia pantalla (rediseno de la
// administracion, 2026-11-15).
function AccionesUsuario({ usuario }: { usuario: Usuario }) {
  const [editando, set_editando] = useState(false);
  const mutacion_activo = usar_actualizar_usuario();

  return (
    <div className={estilos.acciones_fila}>
      <Boton variante="terciario" onClick={() => set_editando(true)}>
        Editar
      </Boton>
      <Boton
        variante="terciario"
        onClick={() =>
          mutacion_activo.mutate({
            usuario_id: usuario.id,
            solicitud: { activo: !usuario.activo },
          })
        }
        disabled={mutacion_activo.isPending}
      >
        {usuario.activo ? "Desactivar" : "Activar"}
      </Boton>
      {editando ? <DialogoUsuario usuario={usuario} al_cerrar={() => set_editando(false)} /> : null}
    </div>
  );
}

const _COLUMNAS: ColumnaTabla<Usuario>[] = [
  { clave: "nombres", encabezado: "Nombres" },
  { clave: "nombre_usuario", encabezado: "Usuario" },
  { clave: "roles", encabezado: "Roles", formatear: (fila) => etiquetas_roles(fila.roles) },
  {
    clave: "activo",
    encabezado: "Estado",
    formatear: (fila) => (
      <span className={fila.activo ? estilos.estado_activo : estilos.estado_inactivo}>
        {fila.activo ? "Activo" : "Inactivo"}
      </span>
    ),
  },
  { clave: "id", encabezado: "", formatear: (fila) => <AccionesUsuario usuario={fila} /> },
];

export function AdministracionUsuarios() {
  const [creando, set_creando] = useState(false);
  const consulta = usar_lista_usuarios();

  return (
    <div>
      <TituloPagina
        titulo="Usuarios"
        acciones={
          <Boton variante="primario" onClick={() => set_creando(true)}>
            Crear usuario
          </Boton>
        }
      />
      <div className={estilos.seccion}>
        <TablaDatos
          columnas={_COLUMNAS}
          filas={consulta.data ?? []}
          obtener_clave={(fila) => fila.id}
          cargando={consulta.isPending}
          error={consulta.error}
          mensaje_vacio="No hay usuarios registrados."
        />
      </div>
      {creando ? <DialogoUsuario usuario={null} al_cerrar={() => set_creando(false)} /> : null}
    </div>
  );
}
