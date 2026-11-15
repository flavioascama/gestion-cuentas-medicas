import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";
import type { RespuestaCompletitudCuenta } from "../../api/cuentas";
import { Boton } from "../../componentes_base/boton";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_completitud_cuenta } from "./usar_cuentas";
import estilos from "./panel_completitud_cuenta.module.css";
import estilos_seccion from "./detalle_cuenta.module.css";

type Pieza = RespuestaCompletitudCuenta["piezas"][number];
type Rol = "analista" | "auditor";

function SugerenciaSeccion({ nombre }: { nombre: string }) {
  return <span className={estilos_seccion.etiqueta_dato}>Ver "{nombre}"</span>;
}

const _ACCIONES: Record<string, { rol: Rol; render: (al_codificar: () => void) => ReactNode }> = {
  codificar: {
    rol: "auditor",
    render: (al_codificar) => (
      <Boton variante="terciario" onClick={al_codificar}>
        Codificar
      </Boton>
    ),
  },
  verificar_cobertura: {
    rol: "analista",
    render: () => <SugerenciaSeccion nombre="Acreditación del asegurado" />,
  },
  emitir_comprobante: {
    rol: "analista",
    render: () => <SugerenciaSeccion nombre="Comprobante de pago" />,
  },
};

function AccionPieza({ pieza, al_codificar }: { pieza: Pieza; al_codificar: () => void }) {
  const { sesion } = usar_sesion();

  if (pieza.completa || !pieza.accion) return null;
  const definicion = _ACCIONES[pieza.accion];
  if (!definicion || !sesion?.roles.includes(definicion.rol)) return null;
  return definicion.render(al_codificar);
}

export function PanelCompletitudCuenta({
  cuenta_id,
  al_codificar,
}: {
  cuenta_id: number;
  al_codificar: () => void;
}) {
  const consulta = usar_completitud_cuenta(cuenta_id);
  const cliente_consultas = useQueryClient();
  const estado_cuenta = consulta.data?.estado_cuenta;

  // ConsultarCompletitudCuenta (backend) puede facturar la cuenta como
  // efecto secundario de esta misma consulta (ver su docstring): sin este
  // efecto, la insignia de estado del encabezado (usar_detalle_cuenta,
  // una consulta distinta) se quedaria mostrando "Registrada" hasta el
  // siguiente montaje de la pantalla.
  useEffect(() => {
    if (estado_cuenta) {
      void cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id], exact: true });
    }
  }, [estado_cuenta, cuenta_id, cliente_consultas]);

  if (!consulta.data) return null;
  const completitud = consulta.data;

  return (
    <div className={estilos_seccion.seccion}>
      <div className={estilos_seccion.titulo_seccion}>
        Completitud de la cuenta {completitud.completa ? "(100 %)" : ""}
      </div>
      <div className={estilos.lista}>
        {completitud.piezas.map((pieza) => (
          <div key={pieza.clave} className={estilos.pieza}>
            <span
              className={`${estilos.punto} ${pieza.completa ? estilos.completa : estilos.pendiente}`}
              aria-hidden="true"
            />
            <span className={estilos.etiqueta_pieza}>{pieza.etiqueta}</span>
            <AccionPieza pieza={pieza} al_codificar={al_codificar} />
          </div>
        ))}
      </div>
    </div>
  );
}
