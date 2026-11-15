import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { ErrorApi } from "../../api/cliente_http";
import { Mensaje } from "../../componentes_base/mensaje";
import { FormularioBusquedaCpms } from "./formulario_busqueda_cpms";
import { ResultadosCpms } from "./resultados_cpms";
import { usar_asistente_cpms } from "./usar_asistente_cpms";

interface Propiedades {
  cuenta_id: number;
  al_cerrar: () => void;
}

// Popup, no pantalla aparte (Fase 21): se abre sobre el detalle de la
// cuenta y se cierra sobre el mismo, sin navegar a otra ruta -- el usuario
// nunca pierde el contexto de la cuenta que esta codificando, y "Cuentas"
// en la barra lateral ya no es el unico camino de vuelta si abre esta
// pantalla por error.
export function AsistenteCpms({ cuenta_id, al_cerrar }: Propiedades) {
  const asistente = usar_asistente_cpms(cuenta_id);

  return (
    <Dialogo
      titulo="Codificación asistida (CPMS)"
      al_cerrar={al_cerrar}
      ancho="grande"
      acciones={
        <Boton variante="primario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      {asistente.mensaje_exito ? (
        <Mensaje tipo="exito" texto="Procedimiento confirmado correctamente." />
      ) : null}
      <FormularioBusquedaCpms
        descripcion={asistente.descripcion}
        al_cambiar={asistente.set_descripcion}
        buscando={asistente.buscando}
      />
      {asistente.error ? (
        <Mensaje
          tipo="error"
          texto={
            asistente.error instanceof ErrorApi
              ? asistente.error.message
              : "No se pudo obtener sugerencias."
          }
        />
      ) : null}
      {asistente.resultado ? (
        <ResultadosCpms
          cuenta_id={cuenta_id}
          descripcion={asistente.descripcion}
          resultado={asistente.resultado}
          candidato_elegido={asistente.candidato_elegido}
          al_elegir={asistente.set_candidato_elegido}
          al_confirmar={asistente.cerrar_confirmacion_exitosa}
        />
      ) : null}
    </Dialogo>
  );
}
