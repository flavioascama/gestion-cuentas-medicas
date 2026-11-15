import type { Hallazgo } from "../../api/lotes";
import { MensajeVacio } from "../../componentes_base/mensaje_vacio";
import estilos from "./informe_prevalidacion.module.css";

interface Propiedades {
  hallazgos: Hallazgo[];
}

interface GrupoHallazgos {
  clave: string;
  tabla: string;
  campo_numero: number;
  campo_nombre: string;
  criterio_texto: string;
  hallazgos: Hallazgo[];
}

function agrupar_por_tabla_y_campo(hallazgos: Hallazgo[]): GrupoHallazgos[] {
  const grupos = new Map<string, GrupoHallazgos>();
  for (const hallazgo of hallazgos) {
    const clave = `${hallazgo.tabla}-${hallazgo.campo_numero}`;
    const grupo_existente = grupos.get(clave);
    if (grupo_existente) {
      grupo_existente.hallazgos.push(hallazgo);
    } else {
      grupos.set(clave, {
        clave,
        tabla: hallazgo.tabla,
        campo_numero: hallazgo.campo_numero,
        campo_nombre: hallazgo.campo_nombre,
        criterio_texto: hallazgo.criterio_texto,
        hallazgos: [hallazgo],
      });
    }
  }
  return [...grupos.values()].sort((a, b) => a.clave.localeCompare(b.clave));
}

export function InformePrevalidacion({ hallazgos }: Propiedades) {
  if (hallazgos.length === 0) return <MensajeVacio texto="No se registraron hallazgos." />;

  return (
    <div>
      {agrupar_por_tabla_y_campo(hallazgos).map((grupo) => (
        <div key={grupo.clave} className={estilos.grupo}>
          <div className={estilos.encabezado_grupo}>
            {grupo.tabla}, campo {grupo.campo_numero} ({grupo.campo_nombre})
          </div>
          <div className={estilos.criterio}>{grupo.criterio_texto}</div>
          {grupo.hallazgos.map((hallazgo, indice) => (
            <div
              key={indice}
              className={`${estilos.hallazgo} ${
                hallazgo.severidad === "error"
                  ? estilos.severidad_error
                  : estilos.severidad_advertencia
              }`}
            >
              «{hallazgo.valor}»: {hallazgo.mensaje}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
