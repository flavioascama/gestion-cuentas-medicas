import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AplicacionRutas } from "./rutas";
import { ProveedorSesion } from "./sesion/proveedor_sesion";
import "./estilos/base.css";

// El tema (Fase 39) se aplica antes de montar React: así la pantalla de
// ingreso (fuera de DisenioPrincipal, que es quien alterna el tema en
// caliente) también respeta la preferencia guardada desde el primer pintado.
try {
  document.documentElement.dataset.theme = localStorage.getItem("tema_interfaz") === "oscuro" ? "dark" : "light";
} catch {
  // Almacenamiento no disponible (navegación privada, etc.): se mantiene el tema claro por defecto.
}

const cliente_consultas = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const elemento_raiz = document.getElementById("raiz");
if (!elemento_raiz) throw new Error("No se encontró el elemento #raiz.");

createRoot(elemento_raiz).render(
  <StrictMode>
    <QueryClientProvider client={cliente_consultas}>
      <BrowserRouter>
        <ProveedorSesion>
          <AplicacionRutas />
        </ProveedorSesion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
