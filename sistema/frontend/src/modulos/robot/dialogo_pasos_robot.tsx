import { useQuery } from "@tanstack/react-query";
import { listar_pasos_robot, type PasoRobot } from "../../api/robot";
import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora } from "../../utilidades/formato";

// Los pasos de una tarea del robot, para el administrador: que hizo, en que
// plataforma y a que hora. Sin la imagen de cada paso.
const _PLATAFORMAS: Record<string, string> = {
  acredita_salud: "ACREDITA SALUD",
  tedef_web: "TEDEF Web",
};

const _COLUMNAS: ColumnaTabla<PasoRobot>[] = [
  { clave: "orden", encabezado: "N.°", alinear_centro: true },
  { clave: "descripcion", encabezado: "Paso" },
  {
    clave: "plataforma",
    encabezado: "Plataforma",
    formatear: (fila) => _PLATAFORMAS[fila.plataforma] ?? fila.plataforma,
  },
  {
    clave: "capturado_en",
    encabezado: "Fecha y hora",
    formatear: (fila) => formatear_fecha_hora(fila.capturado_en),
  },
];

export function DialogoPasosRobot({
  trabajo_id,
  titulo,
  al_cerrar,
}: {
  trabajo_id: number;
  titulo: string;
  al_cerrar: () => void;
}) {
  const consulta = useQuery({
    queryKey: ["robot", "pasos", trabajo_id],
    queryFn: () => listar_pasos_robot(trabajo_id),
  });
  return (
    <Dialogo
      titulo={titulo}
      ancho="grande"
      al_cerrar={al_cerrar}
      acciones={
        <Boton variante="secundario" onClick={al_cerrar}>
          Cerrar
        </Boton>
      }
    >
      <TablaDatos
        columnas={_COLUMNAS}
        filas={consulta.data ?? []}
        obtener_clave={(fila) => fila.orden}
        cargando={consulta.isPending}
        error={consulta.error}
        mensaje_vacio="Sin pasos registrados."
      />
    </Dialogo>
  );
}
