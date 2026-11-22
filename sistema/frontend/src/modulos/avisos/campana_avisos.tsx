import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { Aviso } from "../../api/avisos";
import { IconoCampana } from "../../componentes_base/iconos_navegacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { describir_aviso } from "./catalogo_avisos";
import { usar_ahora } from "../../utilidades/usar_ahora";
import { FilaAviso } from "./fila_aviso";
import { pendientes, recibe_avisos, recorrido_de_avisos, usar_avisos } from "./usar_avisos";
import estilos from "./campana_avisos.module.css";

// Rediseno del 2026-11-12 (pedido del usuario): la campana llevaba directo
// a una pagina que se confundia con la pantalla anterior. Ahora abre un
// panel anclado a ella, con encabezado "Avisos", los pendientes mas
// recientes explicados y el acceso a la bandeja completa.

const _EN_PANEL = 5;

function usar_cierre_exterior(abierto: boolean, al_cerrar: () => void) {
  const contenedor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const al_clic = (evento: MouseEvent) => {
      if (!contenedor.current?.contains(evento.target as Node)) al_cerrar();
    };
    const al_tecla = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") al_cerrar();
    };
    document.addEventListener("mousedown", al_clic);
    document.addEventListener("keydown", al_tecla);
    return () => {
      document.removeEventListener("mousedown", al_clic);
      document.removeEventListener("keydown", al_tecla);
    };
  }, [abierto, al_cerrar]);
  return contenedor;
}

function texto_pendientes(cantidad: number): string {
  return `${cantidad} ${cantidad === 1 ? "pendiente" : "pendientes"}`;
}

function PanelAvisos({ avisos, al_cerrar }: { avisos: Aviso[]; al_cerrar: () => void }) {
  const navegar = useNavigate();
  const ahora = usar_ahora();
  const roles = usar_sesion().sesion?.roles ?? [];
  const lista = pendientes(avisos);
  const abrir = (aviso: Aviso) => {
    const destino = describir_aviso(aviso, roles).destino;
    if (!destino) return;
    al_cerrar();
    void navegar(destino, { state: { recorrido: recorrido_de_avisos(lista, aviso, roles) } });
  };

  return (
    <div className={estilos.panel} role="dialog" aria-label="Avisos">
      <div className={estilos.cabecera_panel}>
        <h2 className={estilos.titulo_panel}>Avisos</h2>
        <span className={estilos.resumen}>
          {lista.length === 0 ? "Sin pendientes" : texto_pendientes(lista.length)}
        </span>
      </div>
      <div className={estilos.lista}>
        {lista.length === 0 ? (
          <p className={estilos.vacio}>No tiene avisos pendientes.</p>
        ) : (
          lista
            .slice(0, _EN_PANEL)
            .map((aviso) => (
              <FilaAviso
                key={aviso.evento_id}
                aviso={aviso}
                ahora={ahora}
                compacta
                al_abrir={abrir}
              />
            ))
        )}
      </div>
      <Link to="/avisos" className={estilos.ver_todos} onClick={al_cerrar}>
        Ver todos los avisos ›
      </Link>
    </div>
  );
}

export function CampanaAvisos() {
  const { sesion } = usar_sesion();
  const ubicacion = useLocation();
  const [abierto, set_abierto] = useState(false);
  const habilitada = !!sesion && recibe_avisos(sesion.roles);
  const consulta = usar_avisos(habilitada);
  const contenedor = usar_cierre_exterior(abierto, () => set_abierto(false));

  if (!habilitada) return null;
  const avisos = consulta.data ?? [];
  const cantidad = pendientes(avisos).length;
  const activa = abierto || ubicacion.pathname === "/avisos";
  const etiqueta = cantidad > 0 ? `Avisos: ${texto_pendientes(cantidad)}` : "Avisos";

  return (
    <div className={estilos.contenedor} ref={contenedor}>
      <button
        type="button"
        className={`${estilos.campana} ${activa ? estilos.activa : ""}`}
        onClick={() => set_abierto((anterior) => !anterior)}
        aria-haspopup="dialog"
        aria-expanded={abierto}
        title={etiqueta}
        aria-label={etiqueta}
      >
        <IconoCampana />
        {cantidad > 0 ? (
          <span className={estilos.contador} aria-hidden="true">
            {cantidad > 99 ? "99+" : cantidad}
          </span>
        ) : null}
      </button>
      {abierto ? <PanelAvisos avisos={avisos} al_cerrar={() => set_abierto(false)} /> : null}
    </div>
  );
}
