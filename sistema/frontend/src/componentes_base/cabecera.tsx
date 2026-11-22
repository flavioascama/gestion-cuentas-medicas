import { useEffect, useRef, useState, type ReactNode } from "react";
import { usar_sesion } from "../sesion/contexto_sesion";
import {
  IconoCandado,
  IconoCerrarSesion,
  IconoChevron,
  IconoLuna,
  IconoSol,
} from "./iconos_navegacion";
import { etiquetas_roles } from "./mapa_roles";
import estilos from "./cabecera.module.css";

function obtener_iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  const iniciales = partes.slice(0, 2).map((parte) => parte[0]?.toUpperCase() ?? "");
  return iniciales.join("") || "?";
}

function MenuPerfil({
  al_salir,
  al_cambiar_clave,
}: {
  al_salir: () => void;
  al_cambiar_clave: () => void;
}) {
  return (
    <div className={estilos.menu_perfil} role="menu">
      <button type="button" className={estilos.boton_cerrar_sesion} onClick={al_cambiar_clave}>
        <IconoCandado />
        <span>Cambiar contraseña</span>
      </button>
      <button type="button" className={estilos.boton_cerrar_sesion} onClick={al_salir}>
        <IconoCerrarSesion />
        <span>Cerrar sesión</span>
      </button>
    </div>
  );
}

// Rediseno pedido por el usuario (2026-11-11): perfil, tema y salir
// vivian al pie de la barra lateral (Fase 39); se mudan aqui para
// liberar esa barra -- queda solo con los modulos y su unico boton de
// colapso (el del rincon fijo, ya no hay un segundo boton flotante).
function PerfilCabecera({
  nombre_usuario,
  roles,
  al_salir,
  al_cambiar_clave,
}: {
  nombre_usuario: string;
  roles: string[];
  al_salir: () => void;
  al_cambiar_clave: () => void;
}) {
  const [abierto, set_abierto] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);
  const nombre = usar_sesion().sesion?.nombres ?? nombre_usuario;

  useEffect(() => {
    function al_hacer_clic_fuera(evento: MouseEvent): void {
      if (!contenedor.current?.contains(evento.target as Node)) set_abierto(false);
    }
    document.addEventListener("mousedown", al_hacer_clic_fuera);
    return () => document.removeEventListener("mousedown", al_hacer_clic_fuera);
  }, []);

  return (
    <div className={estilos.perfil} ref={contenedor}>
      <button
        type="button"
        className={estilos.disparador_perfil}
        onClick={() => set_abierto((anterior) => !anterior)}
        aria-expanded={abierto}
      >
        <span className={estilos.avatar}>{obtener_iniciales(nombre)}</span>
        <span className={estilos.datos_perfil}>
          <span className={estilos.nombre_perfil}>{nombre}</span>
          <span className={estilos.rol_perfil} title={etiquetas_roles(roles)}>
            {etiquetas_roles(roles)}
          </span>
        </span>
        <IconoChevron className={abierto ? estilos.chevron_abierto : estilos.chevron_cerrado} />
      </button>
      {abierto ? (
        <MenuPerfil
          al_salir={al_salir}
          al_cambiar_clave={() => {
            set_abierto(false);
            al_cambiar_clave();
          }}
        />
      ) : null}
    </div>
  );
}

interface Propiedades {
  tema: "claro" | "oscuro";
  al_alternar_tema: () => void;
  nombre_usuario: string;
  roles: string[];
  al_salir: () => void;
  al_cambiar_clave: () => void;
  // La campana de avisos vive en modulos/avisos (consulta la API): se
  // recibe ya armada para que componentes_base no dependa de un modulo.
  accion_avisos?: ReactNode;
}

export function Cabecera({
  tema,
  al_alternar_tema,
  nombre_usuario,
  roles,
  al_salir,
  al_cambiar_clave,
  accion_avisos,
}: Propiedades) {
  const etiqueta_tema = tema === "oscuro" ? "Activar modo claro" : "Activar modo oscuro";
  return (
    <header className={estilos.cabecera}>
      <span className={estilos.nombre_sistema}>Gestión de cuentas médicas</span>
      <div className={estilos.acciones}>
        {accion_avisos}
        <button
          type="button"
          className={estilos.boton_tema}
          onClick={al_alternar_tema}
          title={etiqueta_tema}
          aria-label={etiqueta_tema}
        >
          {tema === "oscuro" ? <IconoSol /> : <IconoLuna />}
        </button>
        <PerfilCabecera
          nombre_usuario={nombre_usuario}
          roles={roles}
          al_salir={al_salir}
          al_cambiar_clave={al_cambiar_clave}
        />
      </div>
    </header>
  );
}
