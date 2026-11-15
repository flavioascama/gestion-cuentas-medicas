import { useState } from "react";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { etiquetas_roles } from "../../componentes_base/mapa_roles";
import { Paginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
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

function coincide(usuario: Usuario, busqueda: string): boolean {
  const texto = busqueda.trim().toLowerCase();
  if (!texto) return true;
  return (
    usuario.nombres.toLowerCase().includes(texto) ||
    usuario.nombre_usuario.toLowerCase().includes(texto)
  );
}

function TablaUsuarios() {
  const consulta = usar_lista_usuarios();
  const [busqueda, set_busqueda] = useState("");
  const filtrados = (consulta.data ?? []).filter((usuario) => coincide(usuario, busqueda));
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(filtrados);

  return (
    <div className={estilos.seccion}>
      <div className={estilos.busqueda}>
        <CampoTexto
          etiqueta="Buscar"
          value={busqueda}
          onChange={(evento) => set_busqueda(evento.target.value)}
          placeholder="Nombre o usuario"
        />
      </div>
      <TablaDatos
        columnas={_COLUMNAS}
        filas={filas_pagina}
        obtener_clave={(fila) => fila.id}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio={
          busqueda ? "Ningún usuario coincide con la búsqueda." : "No hay usuarios registrados."
        }
      />
      <Paginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filtrados.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="usuarios"
      />
    </div>
  );
}

export function AdministracionUsuarios() {
  const [creando, set_creando] = useState(false);

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
      <TablaUsuarios />
      {creando ? <DialogoUsuario usuario={null} al_cerrar={() => set_creando(false)} /> : null}
    </div>
  );
}
