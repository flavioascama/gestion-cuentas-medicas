import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { CONFIGURACION_RUTAS, primera_ruta_permitida } from "./configuracion_rutas";
import { DisenioPrincipal } from "./disenio_principal";
import { AdministracionAseguradoras } from "./modulos/administracion/aseguradoras";
import { AdministracionCatalogos } from "./modulos/administracion/catalogos";
import { AdministracionParametros } from "./modulos/administracion/parametros_sistema";
import { AdministracionUsuarios } from "./modulos/administracion/usuarios";
import { Ingreso } from "./modulos/acceso/ingreso";
import { BandejaAvisos } from "./modulos/avisos/bandeja_avisos";
import { BandejaAnulaciones } from "./modulos/cierre/bandeja_anulaciones";
import { BandejaComunicaciones } from "./modulos/comunicaciones/bandeja_comunicaciones";
import { BandejaContingencias } from "./modulos/contingencia/bandeja_contingencias";
import { BandejaCuentas } from "./modulos/cuentas/bandeja_cuentas";
import { DetalleCuenta } from "./modulos/cuentas/detalle_cuenta";
import { BandejaLotes } from "./modulos/lotes/bandeja_lotes";
import { BandejaActividadRobot } from "./modulos/robot/actividad_robot";
import { DetalleLote } from "./modulos/lotes/detalle_lote";
import { PanelIndicadores } from "./modulos/trazabilidad/panel_indicadores";
import { RutaProtegida } from "./sesion/ruta_protegida";
import { usar_sesion } from "./sesion/contexto_sesion";

// Un elemento por cada entrada de CONFIGURACION_RUTAS (misma clave "ruta"):
// separado en un Map, no en el arreglo de configuracion, para que ese
// arreglo se pueda importar desde barra_lateral.tsx sin arrastrar JSX
// (evita el warning de react-refresh de mezclar componentes y datos en un
// mismo archivo exportado). Un Map, no un Record, porque las claves son
// rutas ("/lotes/:lote_id") y no pasan la convencion snake_case que el
// linter exige para propiedades de un objeto literal.
const _ELEMENTOS = new Map<string, ReactNode>([
  ["/cuentas", <BandejaCuentas />],
  ["/cuentas/:cuenta_id", <DetalleCuenta />],
  ["/lotes", <BandejaLotes />],
  ["/lotes/:lote_id", <DetalleLote />],
  ["/comunicaciones", <BandejaComunicaciones />],
  ["/robot", <BandejaActividadRobot />],
  ["/anulaciones", <BandejaAnulaciones />],
  ["/contingencias", <BandejaContingencias />],
  ["/indicadores", <PanelIndicadores />],
  ["/administracion/usuarios", <AdministracionUsuarios />],
  ["/administracion/aseguradoras", <AdministracionAseguradoras />],
  ["/administracion/parametros", <AdministracionParametros />],
  ["/administracion/catalogos", <AdministracionCatalogos />],
  ["/administracion", <Navigate to="/administracion/usuarios" replace />],
  ["/avisos", <BandejaAvisos />],
]);

function RedireccionInicio() {
  const { sesion } = usar_sesion();
  return <Navigate to={primera_ruta_permitida(sesion?.roles ?? [])} replace />;
}

export function AplicacionRutas() {
  return (
    <Routes>
      <Route path="/ingreso" element={<Ingreso />} />
      <Route
        element={
          <RutaProtegida>
            <DisenioPrincipal />
          </RutaProtegida>
        }
      >
        <Route path="/" element={<RedireccionInicio />} />
        {CONFIGURACION_RUTAS.map(({ ruta, roles }) => (
          <Route
            key={ruta}
            path={ruta}
            element={<RutaProtegida roles_permitidos={roles}>{_ELEMENTOS.get(ruta)}</RutaProtegida>}
          />
        ))}
        <Route path="*" element={<RedireccionInicio />} />
      </Route>
    </Routes>
  );
}
