// Barra lateral simplificada (rediseno pedido por el usuario,
// 2026-11-11): solo modulos. El perfil, el tema y "Cerrar sesion" se
// mudaron a la cabecera (componentes_base/cabecera.tsx); el unico
// control para mostrar/ocultar esta barra es el boton del rincon fijo
// (disenio_principal.tsx) -- antes habia un segundo boton flotando en
// el borde de la propia barra, con el mismo efecto, lo que confundia
// cual de los dos usar.

import { NavLink } from "react-router-dom";
import { CONFIGURACION_RUTAS, type DefinicionRuta } from "../configuracion_rutas";
import { usar_sesion } from "../sesion/contexto_sesion";
import {
  IconoAdministracion,
  IconoAnulaciones,
  IconoAseguradoras,
  IconoCatalogos,
  IconoComunicaciones,
  IconoContingencias,
  IconoCuentas,
  IconoIndicadores,
  IconoLotes,
  IconoRobot,
  IconoUsuarios,
} from "./iconos_navegacion";
import estilos from "./barra_lateral.module.css";

const _ICONOS = new Map([
  ["/cuentas", IconoCuentas],
  ["/lotes", IconoLotes],
  ["/comunicaciones", IconoComunicaciones],
  ["/robot", IconoRobot],
  ["/anulaciones", IconoAnulaciones],
  ["/contingencias", IconoContingencias],
  ["/indicadores", IconoIndicadores],
  ["/administracion/usuarios", IconoUsuarios],
  ["/administracion/aseguradoras", IconoAseguradoras],
  ["/administracion/parametros", IconoAdministracion],
  ["/administracion/catalogos", IconoCatalogos],
]);

function icono_de_ruta(ruta: string) {
  return _ICONOS.get(ruta) ?? null;
}

function modulos_visibles(roles_usuario: string[]): DefinicionRuta[] {
  return CONFIGURACION_RUTAS.filter(
    (definicion) =>
      definicion.etiqueta !== undefined &&
      (definicion.roles === undefined ||
        definicion.roles.some((rol) => roles_usuario.includes(rol))),
  );
}

function EnlaceModulo({ modulo, abierta }: { modulo: DefinicionRuta; abierta: boolean }) {
  const Icono = icono_de_ruta(modulo.ruta);
  return (
    <NavLink
      to={modulo.ruta}
      tabIndex={abierta ? undefined : -1}
      className={({ isActive }) => `${estilos.enlace} ${isActive ? estilos.enlace_activo : ""}`}
    >
      {Icono ? <Icono /> : null}
      <span>{modulo.etiqueta}</span>
    </NavLink>
  );
}

export function BarraLateral({ abierta }: { abierta: boolean }) {
  const { sesion } = usar_sesion();
  const modulos = modulos_visibles(sesion?.roles ?? []);

  return (
    <nav
      className={`${estilos.barra} ${abierta ? "" : estilos.barra_cerrada}`}
      aria-label="Módulos del sistema"
      aria-hidden={!abierta}
    >
      <div className={estilos.contenido}>
        <span className={estilos.etiqueta_seccion}>Módulos</span>
        <div className={estilos.enlaces}>
          {modulos.map((modulo) => (
            <EnlaceModulo key={modulo.ruta} modulo={modulo} abierta={abierta} />
          ))}
        </div>
      </div>
    </nav>
  );
}
