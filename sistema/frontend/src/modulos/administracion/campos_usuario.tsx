import type { NombreRol } from "../../api/auth";
import { CampoTexto } from "../../componentes_base/campo_texto";
import type { usar_formulario_usuario } from "./usar_formulario_usuario";
import estilos from "./administracion.module.css";

const _ROLES: { valor: NombreRol; etiqueta: string }[] = [
  { valor: "analista", etiqueta: "Analista" },
  { valor: "auditor", etiqueta: "Auditor" },
  { valor: "jefe", etiqueta: "Jefe" },
  { valor: "administrador", etiqueta: "Administrador" },
];

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
          value={formulario.nombre_usuario}
          onChange={(evento) => formulario.set_nombre_usuario(evento.target.value)}
          placeholder="ana.analista"
        />
      ) : null}
      <CampoTexto
        etiqueta="Nombres completos"
        value={formulario.nombres}
        onChange={(evento) => formulario.set_nombres(evento.target.value)}
      />
      {!formulario.es_edicion ? (
        <CampoTexto
          etiqueta="Clave temporal"
          type="password"
          value={formulario.clave}
          onChange={(evento) => formulario.set_clave(evento.target.value)}
        />
      ) : null}
      <div>
        <span className={estilos.etiqueta_roles}>Roles</span>
        <div className={estilos.lista_roles}>
          {_ROLES.map((rol) => (
            <div key={rol.valor} className={estilos.fila_rol}>
              <input
                type="checkbox"
                id={`rol_${rol.valor}`}
                checked={formulario.roles.has(rol.valor)}
                onChange={() => formulario.alternar_rol(rol.valor)}
              />
              <label htmlFor={`rol_${rol.valor}`}>{rol.etiqueta}</label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
