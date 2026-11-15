import type { CandidatoCpms } from "../../api/cpms";
import { Boton } from "../../componentes_base/boton";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import estilos from "./asistente_cpms.module.css";

interface Propiedades {
  candidatos: CandidatoCpms[];
  puede_confirmar: boolean;
  al_elegir: (candidato: CandidatoCpms) => void;
}

export function TablaCandidatos({ candidatos, puede_confirmar, al_elegir }: Propiedades) {
  const columnas: ColumnaTabla<CandidatoCpms>[] = [
    { clave: "posicion", encabezado: "N.°", alinear_derecha: true },
    { clave: "codigo", encabezado: "Código" },
    { clave: "denominacion", encabezado: "Denominación" },
    {
      clave: "nombre_grupo",
      encabezado: "Jerarquía",
      formatear: (fila) => (
        <span className={estilos.jerarquia}>
          {fila.nombre_grupo} / {fila.nombre_seccion} / {fila.nombre_subseccion}
        </span>
      ),
    },
    {
      clave: "codigo",
      encabezado: "",
      formatear: (fila) => (
        <Boton variante="terciario" onClick={() => al_elegir(fila)} disabled={!puede_confirmar}>
          Confirmar
        </Boton>
      ),
    },
  ];

  return (
    <TablaDatos
      columnas={columnas}
      filas={candidatos}
      obtener_clave={(fila) => fila.posicion}
      mensaje_vacio="No se encontraron candidatos para esa descripción."
    />
  );
}
