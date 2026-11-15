import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { BarraLateral } from "./componentes_base/barra_lateral";
import { Cabecera } from "./componentes_base/cabecera";
import { IconoMenu } from "./componentes_base/iconos_navegacion";
import { CampanaAvisos } from "./modulos/avisos/campana_avisos";
import estilos from "./disenio_principal.module.css";
import { usar_sesion } from "./sesion/contexto_sesion";

type Tema = "claro" | "oscuro";

const _CLAVE_BARRA_ABIERTA = "barra_lateral_abierta";
const _CLAVE_TEMA = "tema_interfaz";

function leer_preferencia_barra(): boolean {
  try {
    return localStorage.getItem(_CLAVE_BARRA_ABIERTA) !== "false";
  } catch {
    return true;
  }
}

function guardar_preferencia_barra(abierta: boolean): void {
  try {
    localStorage.setItem(_CLAVE_BARRA_ABIERTA, String(abierta));
  } catch {
    // Almacenamiento no disponible (navegación privada, etc.): no es crítico.
  }
}

function leer_preferencia_tema(): Tema {
  try {
    return localStorage.getItem(_CLAVE_TEMA) === "oscuro" ? "oscuro" : "claro";
  } catch {
    return "claro";
  }
}

function guardar_preferencia_tema(tema: Tema): void {
  try {
    localStorage.setItem(_CLAVE_TEMA, tema);
  } catch {
    // Almacenamiento no disponible (navegación privada, etc.): no es crítico.
  }
}

function RinconMenu({
  barra_abierta,
  al_alternar_barra,
}: {
  barra_abierta: boolean;
  al_alternar_barra: () => void;
}) {
  return (
    <div className={estilos.rincon}>
      <button
        type="button"
        className={estilos.boton_menu}
        onClick={al_alternar_barra}
        title={barra_abierta ? "Ocultar menú" : "Mostrar menú"}
        aria-label={barra_abierta ? "Ocultar menú" : "Mostrar menú"}
        aria-expanded={barra_abierta}
      >
        <IconoMenu />
      </button>
    </div>
  );
}

export function DisenioPrincipal() {
  const { sesion, cerrar_sesion } = usar_sesion();
  const navegar = useNavigate();
  const [barra_abierta, set_barra_abierta] = useState(leer_preferencia_barra);
  const [tema, set_tema] = useState<Tema>(leer_preferencia_tema);

  useEffect(() => {
    document.documentElement.dataset.theme = tema === "oscuro" ? "dark" : "light";
  }, [tema]);

  const manejar_salida = () => {
    void cerrar_sesion().then(() => navegar("/ingreso", { replace: true }));
  };

  const alternar_barra = () => {
    set_barra_abierta((anterior) => {
      const nuevo_valor = !anterior;
      guardar_preferencia_barra(nuevo_valor);
      return nuevo_valor;
    });
  };

  const alternar_tema = () => {
    set_tema((anterior) => {
      const nuevo_valor: Tema = anterior === "oscuro" ? "claro" : "oscuro";
      guardar_preferencia_tema(nuevo_valor);
      return nuevo_valor;
    });
  };

  if (!sesion) return null;

  return (
    <div className={estilos.envoltorio}>
      <RinconMenu barra_abierta={barra_abierta} al_alternar_barra={alternar_barra} />
      <BarraLateral abierta={barra_abierta} />
      <div className={estilos.columna}>
        <Cabecera
          tema={tema}
          al_alternar_tema={alternar_tema}
          nombre_usuario={sesion.nombre_usuario}
          roles={sesion.roles}
          al_salir={manejar_salida}
          accion_avisos={<CampanaAvisos />}
        />
        <main className={estilos.contenido}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
