import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { obtener_sesion_actual } from "../../api/auth";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Mensaje } from "../../componentes_base/mensaje";
import { primera_ruta_permitida } from "../../configuracion_rutas";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { IconoCandado, IconoEscudo, IconoFlechaDerecha, IconoPersona } from "./iconos_ingreso";
import { usar_formulario_ingreso } from "./usar_formulario_ingreso";
import estilos from "./ingreso.module.css";

export function Ingreso() {
  const { sesion } = usar_sesion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const formulario = usar_formulario_ingreso(() => {
    const destino = primera_ruta_permitida(obtener_sesion_actual()?.roles ?? []);
    void navegar(destino, { replace: true });
  });

  if (sesion) {
    const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? primera_ruta_permitida(sesion.roles);
    return <Navigate to={destino} replace />;
  }

  return (
    <div className={estilos.envoltorio}>
      <form className={estilos.tarjeta} onSubmit={formulario.manejar_envio}>
        <div className={estilos.titulo}>Gestión de cuentas médicas</div>
        {formulario.error ? <Mensaje tipo="error" texto={formulario.error} /> : null}
        <CampoTexto
          etiqueta="Nombre de usuario"
          icono={<IconoPersona />}
          value={formulario.nombre_usuario}
          onChange={(evento) => formulario.set_nombre_usuario(evento.target.value)}
          autoFocus
          required
        />
        <CampoTexto
          etiqueta="Contraseña"
          type="password"
          icono={<IconoCandado />}
          value={formulario.clave}
          onChange={(evento) => formulario.set_clave(evento.target.value)}
          required
        />
        <Boton
          type="submit"
          variante="primario"
          className={estilos.boton_enviar}
          disabled={formulario.enviando}
        >
          {formulario.enviando ? "Ingresando…" : "Ingresar"}
          <IconoFlechaDerecha />
        </Boton>
        <p className={estilos.confianza}>
          <IconoEscudo />
          Tu sesión y tus datos están protegidos
        </p>
      </form>
    </div>
  );
}
