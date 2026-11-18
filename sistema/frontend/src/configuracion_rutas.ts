import type { NombreRol } from "./api/auth";

export interface DefinicionRuta {
  ruta: string;
  // Sin "etiqueta" la ruta no aparece en la barra lateral (rutas de
  // detalle, ej. "/lotes/:lote_id") -- pero sigue protegida por rol igual.
  etiqueta?: string;
  roles?: NombreRol[];
}

// Fuente unica de verdad de que rol ve que pantalla: tanto el router
// (rutas.tsx, que agrega el elemento de cada una) como la barra lateral
// (barra_lateral.tsx, que solo necesita ruta/etiqueta/roles) leen de aqui,
// para que nunca puedan desalinearse.
export const CONFIGURACION_RUTAS: DefinicionRuta[] = [
  {
    ruta: "/cuentas",
    etiqueta: "Cuentas",
    // Tesoreria se agrego en la Fase 30, al consolidar la matriz de
    // permisos (Tabla 46: "consultar las cuentas y su detalle").
    roles: ["analista", "auditor", "jefe", "tesoreria"],
  },
  { ruta: "/cuentas/:cuenta_id", roles: ["analista", "auditor", "jefe", "tesoreria"] },
  { ruta: "/lotes", etiqueta: "Lotes", roles: ["analista", "jefe"] },
  { ruta: "/lotes/:lote_id", roles: ["analista", "jefe"] },
  // Todo lo que las aseguradoras comunican por su portal y por correo,
  // incluidos los correos que una persona debe revisar (2026-11-15).
  {
    ruta: "/comunicaciones",
    etiqueta: "Comunicaciones",
    roles: ["analista", "auditor", "jefe", "tesoreria"],
  },
  // CU-13/RF-21 (Fase 28, 31): bandeja del jefe para aprobar o rechazar
  // las solicitudes de anulacion -- no vive dentro de una cuenta porque
  // reune solicitudes de cualquier cuenta.
  { ruta: "/anulaciones", etiqueta: "Anulaciones", roles: ["jefe"] },
  // C-18 (verificacion de cumplimiento, 2026-11-12): revision posterior de
  // los resultados registrados en modo de contingencia.
  { ruta: "/contingencias", etiqueta: "Contingencias", roles: ["jefe"] },
  // CU-15 (Fase 29, 31): panel de control gerencial.
  { ruta: "/indicadores", etiqueta: "Panel gerencial", roles: ["jefe", "gerente"] },
  // Administracion dividida por tarea (rediseno 2026-11-15): usuarios,
  // aseguradoras, parametros y catalogos, cada uno en su propia pantalla
  // en vez de apilados en una sola. "/administracion" queda sin etiqueta
  // y redirige a usuarios.
  { ruta: "/administracion/usuarios", etiqueta: "Usuarios", roles: ["administrador"] },
  { ruta: "/administracion/aseguradoras", etiqueta: "Aseguradoras", roles: ["administrador"] },
  { ruta: "/administracion/parametros", etiqueta: "Parámetros", roles: ["administrador"] },
  { ruta: "/administracion/catalogos", etiqueta: "Catálogos", roles: ["administrador"] },
  // Registro de lo que hizo el robot: tarea, usuario que la pidio y hora.
  // Solo el administrador (2026-11-18); no es parte del trabajo diario.
  { ruta: "/robot", etiqueta: "Actividad del robot", roles: ["administrador"] },
  { ruta: "/administracion", roles: ["administrador"] },
  // Bandeja de avisos (verificacion de cumplimiento, 2026-11-12): sin
  // etiqueta, se abre desde la campana de la cabecera. Mismos roles que
  // ROLES_CON_AVISOS (modulos/avisos/usar_avisos.ts).
  { ruta: "/avisos", roles: ["analista", "auditor", "jefe", "tesoreria", "administrador"] },
];

// La pantalla de inicio no puede ser siempre "/cuentas": administrador
// y gerente no tienen ese rol en su lista de roles permitidos, y caer
// ahi los deja viendo "su rol no tiene permiso" apenas inician sesion.
// Se redirige en cambio a la primera ruta con "etiqueta" (una pantalla
// real, no una ruta de detalle) cuyos roles incluyan alguno de los del
// usuario, en el mismo orden en que aparecen arriba.
export function primera_ruta_permitida(roles_usuario: NombreRol[]): string {
  const primera = CONFIGURACION_RUTAS.find(
    (definicion) =>
      definicion.etiqueta !== undefined &&
      definicion.roles?.some((rol) => roles_usuario.includes(rol)),
  );
  return primera?.ruta ?? "/ingreso";
}
