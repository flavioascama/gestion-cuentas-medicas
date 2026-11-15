import { useState } from "react";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { etiqueta_rol } from "../../componentes_base/mapa_roles";
import { DialogoUsuario } from "./dialogo_usuario";
import { usar_actualizar_usuario, usar_lista_usuarios } from "./usar_usuarios";
import estilos from "./administracion.module.css";

function FilaAcciones({ usuario }: { usuario: Usuario }) {
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

export function SeccionUsuarios() {
  const [mostrar_dialogo, set_mostrar_dialogo] = useState(false);
  const consulta = usar_lista_usuarios();

  const columnas: ColumnaTabla<Usuario>[] = [
    { clave: "nombre_usuario", encabezado: "Usuario" },
    { clave: "nombres", encabezado: "Nombres" },
    {
      clave: "roles",
      encabezado: "Roles",
      formatear: (fila) => fila.roles.map(etiqueta_rol).join(", "),
    },
    {
      clave: "activo",
      encabezado: "Estado",
      formatear: (fila) => (
        <span className={fila.activo ? estilos.estado_activo : estilos.estado_inactivo}>
          {fila.activo ? "Activo" : "Inactivo"}
        </span>
      ),
    },
    {
      clave: "id",
      encabezado: "",
      formatear: (fila) => <FilaAcciones usuario={fila} />,
    },
  ];

  return (
    <div className={estilos.seccion}>
      <div className={estilos.cabecera_seccion}>
        <div className={estilos.titulo_seccion}>Usuarios</div>
        <Boton variante="secundario" onClick={() => set_mostrar_dialogo(true)}>
          Crear usuario
        </Boton>
      </div>
      <TablaDatos
        columnas={columnas}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="No hay usuarios registrados."
      />
      {mostrar_dialogo ? (
        <DialogoUsuario usuario={null} al_cerrar={() => set_mostrar_dialogo(false)} />
      ) : null}
    </div>
  );
}
