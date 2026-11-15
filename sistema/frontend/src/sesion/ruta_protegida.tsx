import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import type { NombreRol } from "../api/auth";
import { usar_sesion } from "./contexto_sesion";

interface Propiedades {
  children: ReactNode;
  roles_permitidos?: NombreRol[];
}

export function RutaProtegida({ children, roles_permitidos }: Propiedades) {
  const { sesion } = usar_sesion();

  if (sesion === null) return <Navigate to="/ingreso" replace />;

  if (roles_permitidos && !roles_permitidos.some((rol) => sesion.roles.includes(rol))) {
    return <div role="alert">Su rol no tiene permiso para ver esta pantalla.</div>;
  }

  return <>{children}</>;
}
