import type { NombreRol } from "../../api/auth";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { etiqueta_rol, roles_fuera_de_perfiles } from "../../componentes_base/mapa_roles";
import type { usar_formulario_usuario } from "./usar_formulario_usuario";
import estilos from "./administracion.module.css";

const _ROLES: { valor: NombreRol; etiqueta: string }[] = [
  { valor: "analista", etiqueta: "Analista" },
  { valor: "auditor", etiqueta: "Auditor" },
  { valor: "jefe", etiqueta: "Jefe" },
  { valor: "administrador", etiqueta: "Administrador" },
];

type Formulario = ReturnType<typeof usar_formulario_usuario>;

// Roles que la persona ya tiene y que no son de ningun perfil: se ven
// marcados y no se cambian desde aqui; al guardar se conservan.
function RolesFijos({ formulario }: { formulario: Formulario }) {
  const perfiles = _ROLES.map((rol) => rol.valor);
  return roles_fuera_de_perfiles(formulario.roles, perfiles).map((rol) => (
    <div key={rol} className={estilos.fila_rol}>
      <input type="checkbox" id={`rol_${rol}`} checked disabled readOnly />
      <label htmlFor={`rol_${rol}`}>{etiqueta_rol(rol)}</label>
    </div>
  ));
}

function SeleccionRoles({ formulario }: { formulario: Formulario }) {
  return (
    <div>
      <span className={estilos.etiqueta_roles}>Roles *</span>
      <div className={estilos.lista_roles}>
        {_ROLES.map((rol) => (
          <div key={rol.valor} className={estilos.fila_rol}>
            <input
              type="checkbox"
              id={`rol_${rol.valor}`}
              checked={formulario.roles.has(rol.valor)}
              disabled={formulario.es_propio}
              onChange={() => formulario.alternar_rol(rol.valor)}
            />
            <label htmlFor={`rol_${rol.valor}`}>{rol.etiqueta}</label>
          </div>
        ))}
        <RolesFijos formulario={formulario} />
      </div>
    </div>
  );
}

export function CamposUsuario({
  formulario,
}: {
  formulario: ReturnType<typeof usar_formulario_usuario>;
}) {
  return (
    <div className={estilos.formulario_usuario}>
      {!formulario.es_edicion ? (
        <CampoTexto
          etiqueta="Nombre de usuario"
          obligatorio
          value={formulario.nombre_usuario}
          onChange={(evento) => formulario.set_nombre_usuario(evento.target.value)}
          placeholder="ana.analista"
        />
      ) : null}
      <CampoTexto
        etiqueta="Nombres completos"
        obligatorio
        value={formulario.nombres}
        onChange={(evento) => formulario.set_nombres(evento.target.value)}
      />
      {!formulario.es_edicion ? (
        <CampoTexto
          etiqueta="Contraseña temporal"
          obligatorio
          type="password"
          value={formulario.clave}
          error={formulario.error_clave}
          onChange={(evento) => formulario.set_clave(evento.target.value)}
        />
      ) : null}
      <SeleccionRoles formulario={formulario} />
    </div>
  );
}
