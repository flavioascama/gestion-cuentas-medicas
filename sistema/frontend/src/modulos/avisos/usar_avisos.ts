import { useQuery } from "@tanstack/react-query";
import { listar_avisos, type Aviso } from "../../api/avisos";
import type { NombreRol } from "../../api/auth";
import type { Recorrido } from "../../navegacion/recorrido";
import { describir_aviso } from "./catalogo_avisos";

// Roles con al menos un tipo de aviso en el catalogo del backend
// (app/dominio/avisos/valores.py). El gerente no recibe avisos: la
// tesis escala los plazos al jefe, no a gerencia.
export const ROLES_CON_AVISOS: NombreRol[] = [
  "analista",
  "auditor",
  "jefe",
  "tesoreria",
  "administrador",
];

export function recibe_avisos(roles: NombreRol[]): boolean {
  return roles.some((rol) => ROLES_CON_AVISOS.includes(rol));
}

// Los avisos se leen del almacen de eventos y llegan sin que nadie
// recargue la pagina: se vuelven a pedir cada minuto.
const _INTERVALO_REFRESCO_MS = 60_000;

export function usar_avisos(habilitado: boolean) {
  return useQuery({
    queryKey: ["avisos"],
    queryFn: listar_avisos,
    enabled: habilitado,
    refetchInterval: _INTERVALO_REFRESCO_MS,
  });
}

export function pendientes(avisos: Aviso[]): Aviso[] {
  return avisos.filter((aviso) => !aviso.atendido);
}

// Recorrido por los avisos de una lista: al abrir uno, el detalle de la
// cuenta o del lote muestra "Aviso 3 de 12", por que se esta ahi, y deja
// pasar al anterior o al siguiente sin volver a la bandeja.
export function recorrido_de_avisos(
  avisos: Aviso[],
  aviso_abierto: Aviso,
  roles: NombreRol[],
): Recorrido | null {
  const con_destino = avisos.filter((aviso) => describir_aviso(aviso, roles).destino !== null);
  const indice = con_destino.findIndex((aviso) => aviso.evento_id === aviso_abierto.evento_id);
  if (indice < 0) return null;
  return {
    migas: [{ etiqueta: "Avisos", ruta: "/avisos" }],
    volver: { etiqueta: "Volver a avisos", ruta: "/avisos" },
    nombre: "Aviso",
    indice,
    pasos: con_destino.map((aviso) => {
      const descripcion = describir_aviso(aviso, roles);
      return {
        ruta: descripcion.destino ?? "/avisos",
        etiqueta: descripcion.titulo,
        detalle: `${descripcion.titulo}. ${descripcion.que_paso}`,
      };
    }),
  };
}
