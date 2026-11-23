import { useState } from "react";
import type { Usuario } from "../../api/usuarios";
import { Boton } from "../../componentes_base/boton";
import { DialogoConfirmar } from "../../componentes_base/dialogo_confirmar";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { etiquetas_roles } from "../../componentes_base/mapa_roles";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { TituloPagina } from "../../componentes_base/titulo_pagina";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { BotonEliminarUsuario } from "./boton_eliminar_usuario";
import { DialogoRestablecerClave } from "./dialogo_restablecer_clave";
import { DialogoUsuario } from "./dialogo_usuario";
import { usar_actualizar_usuario, usar_lista_usuarios } from "./usar_usuarios";
import estilos from "./administracion.module.css";

// CU-18: gestion de usuarios en su propia pantalla (rediseno de la
// administracion, 2026-11-15).
function AccionesUsuario({ usuario }: { usuario: Usuario }) {
  const [editando, set_editando] = useState(false);
  const [restableciendo, set_restableciendo] = useState(false);
  const [desactivando, set_desactivando] = useState(false);
  const mutacion_activo = usar_actualizar_usuario();
  const es_propio = usar_sesion().sesion?.usuario_id === usuario.id;
  const cambiar_activo = () =>
    mutacion_activo.mutate({ usuario_id: usuario.id, solicitud: { activo: !usuario.activo } });

  return (
    <div>
      <div className={estilos.acciones_fila}>
        <Boton variante="terciario" onClick={() => set_editando(true)}>
          Editar
        </Boton>
        <Boton variante="terciario" onClick={() => set_restableciendo(true)} disabled={es_propio}>
          Restablecer contraseña
        </Boton>
        <Boton
          variante="terciario"
          onClick={() => (usuario.activo ? set_desactivando(true) : cambiar_activo())}
          disabled={mutacion_activo.isPending || es_propio}
        >
          {usuario.activo ? "Desactivar" : "Activar"}
        </Boton>
        <BotonEliminarUsuario usuario={usuario} disabled={es_propio} />
        {desactivando ? (
          <DialogoConfirmar
            titulo="Desactivar usuario"
            texto={`${usuario.nombre_usuario} ya no podrá ingresar al sistema.`}
            texto_confirmar="Desactivar"
            al_confirmar={cambiar_activo}
            al_cerrar={() => set_desactivando(false)}
          />
        ) : null}
        {editando ? (
          <DialogoUsuario usuario={usuario} al_cerrar={() => set_editando(false)} />
        ) : null}
        {restableciendo ? (
          <DialogoRestablecerClave usuario={usuario} al_cerrar={() => set_restableciendo(false)} />
        ) : null}
      </div>
      <MensajeErrorMutacion
        error={mutacion_activo.error}
        texto_por_defecto="No se pudo cambiar el estado del usuario."
      />
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
  // Primero los activos; dentro de cada grupo se conserva el orden recibido.
  const filtrados = (consulta.data ?? [])
    .filter((usuario) => coincide(usuario, busqueda))
    .sort((a, b) => Number(b.activo) - Number(a.activo));
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
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={filtrados.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="usuarios"
      >
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
      </ConPaginacion>
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
