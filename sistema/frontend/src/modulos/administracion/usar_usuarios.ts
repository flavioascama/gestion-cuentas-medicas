import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  actualizar_usuario,
  crear_usuario,
  eliminar_usuario,
  listar_usuarios,
  restablecer_clave_usuario,
  type SolicitudActualizarUsuario,
  type SolicitudCrearUsuario,
} from "../../api/usuarios";

const _CLAVE = ["administracion", "usuarios"];

export function usar_lista_usuarios() {
  return useQuery({ queryKey: _CLAVE, queryFn: listar_usuarios });
}

export function usar_crear_usuario() {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: (solicitud: SolicitudCrearUsuario) => crear_usuario(solicitud),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: _CLAVE }),
  });
}

export function usar_actualizar_usuario() {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: ({
      usuario_id,
      solicitud,
    }: {
      usuario_id: number;
      solicitud: SolicitudActualizarUsuario;
    }) => actualizar_usuario(usuario_id, solicitud),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: _CLAVE }),
  });
}

export function usar_eliminar_usuario() {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: (usuario_id: number) => eliminar_usuario(usuario_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: _CLAVE }),
  });
}

export function usar_restablecer_clave() {
  return useMutation({
    mutationFn: ({ usuario_id, clave }: { usuario_id: number; clave: string }) =>
      restablecer_clave_usuario(usuario_id, clave),
  });
}
