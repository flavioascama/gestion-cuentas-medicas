import { Boton } from "../../componentes_base/boton";
import { Mensaje } from "../../componentes_base/mensaje";
import estilos from "../cuentas/detalle_cuenta.module.css";
import { usar_sesion_automatica } from "./usar_sesion_automatica";

interface Propiedades {
  plataforma: string;
  nombre: string;
  // Una tarea en curso esta esperando la sesion con la plataforma.
  necesita: boolean;
}

// Lo unico que la persona ve de la sesion con una plataforma externa
// (ACREDITA SALUD, TEDEF Web): el dialogo del codigo de verificacion y, si
// la plataforma no acepta la conexion, el aviso. La sesion se pide sola
// mientras una tarea la necesita; no se avisa que hace falta ni que vencio.
export function SesionPlataforma({ plataforma, nombre, necesita }: Propiedades) {
  const sesion = usar_sesion_automatica(plataforma, necesita);
  return (
    <>
      {sesion.dialogo}
      {sesion.espera_codigo ? (
        <div className={estilos.fila_accion}>
          <Boton variante="secundario" onClick={sesion.abrir_codigo}>
            Ingresar el código de verificación
          </Boton>
        </div>
      ) : null}
      {sesion.sin_conexion ? (
        <div className={estilos.fila_accion}>
          <Mensaje tipo="error" texto={`No se pudo conectar con ${nombre}.`} />
          <Boton variante="secundario" onClick={sesion.reintentar}>
            Reintentar
          </Boton>
        </div>
      ) : null}
    </>
  );
}
