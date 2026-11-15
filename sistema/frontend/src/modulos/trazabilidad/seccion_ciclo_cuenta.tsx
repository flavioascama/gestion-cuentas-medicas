import { useNavigate } from "react-router-dom";
import type { CicloCuenta, IndicadoresCiclo } from "../../api/trazabilidad";
import { EtiquetaEstado } from "../../componentes_base/etiqueta_estado";
import { TablaDatos, type ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_entero, formatear_horas } from "./formato_indicadores";
import estilos from "./seccion_ciclo_cuenta.module.css";

// R3.4 (Tabla 5): "tiempo de ciclo por cuenta". Agregado a partir de la
// verificacion de cumplimiento del 12 de noviembre: el panel solo tenia
// el promedio por etapa, que no dice cuanto tarda una cuenta en cobrarse
// ni cuales llevan mas tiempo detenidas.

function Cifra({
  etiqueta,
  valor,
  contexto,
}: {
  etiqueta: string;
  valor: string;
  contexto: string;
}) {
  return (
    <div className={estilos.cifra}>
      <span className={estilos.etiqueta}>{etiqueta}</span>
      <span className={estilos.valor}>{valor}</span>
      <span className={estilos.contexto}>{contexto}</span>
    </div>
  );
}

function horas_o_guion(horas: number | null | undefined): string {
  return horas === null || horas === undefined ? "—" : formatear_horas(horas);
}

const _COLUMNAS: ColumnaTabla<CicloCuenta>[] = [
  {
    clave: "identificacion_interna",
    encabezado: "Cuenta",
    formatear: (fila) => <span className={estilos.cuenta}>{fila.identificacion_interna}</span>,
  },
  {
    clave: "estado",
    encabezado: "Estado actual",
    formatear: (fila) => <EtiquetaEstado estado={fila.estado} />,
  },
  {
    clave: "horas",
    encabezado: "Tiempo en el ciclo",
    alinear_derecha: true,
    formatear: (fila) => formatear_horas(fila.horas),
  },
];

const _ESTADOS_TERMINALES = new Set(["CERRADA", "ANULADA"]);

// Solo se mide una cuenta que tiene eventos de estado (la medicion sale
// del almacen de eventos); las cargadas sin historial no se pueden medir,
// y el texto lo dice en vez de presentar una fraccion como el total.
function contexto_abiertas(indicadores: IndicadoresCiclo): string {
  const medidas = indicadores.tiempo_ciclo_cuentas.cuentas_abiertas;
  const total = indicadores.distribucion_por_estado
    .filter((fila) => !_ESTADOS_TERMINALES.has(fila.estado))
    .reduce((suma, fila) => suma + fila.cantidad, 0);
  if (medidas === total) return `${formatear_entero(total)} cuentas en curso`;
  return `${formatear_entero(medidas)} de ${formatear_entero(total)} cuentas en curso tienen eventos para medirse`;
}

export function SeccionCicloCuenta({ indicadores }: { indicadores: IndicadoresCiclo }) {
  const navegar = useNavigate();
  const ciclo = indicadores.tiempo_ciclo_cuentas;
  return (
    <section className={estilos.tarjeta} aria-labelledby="titulo_ciclo_cuenta">
      <h2 id="titulo_ciclo_cuenta" className={estilos.titulo}>
        Tiempo de ciclo por cuenta
      </h2>
      <p className={estilos.subtitulo}>
        Desde el registro de la cuenta hasta su cierre; para las abiertas, hasta hoy.
      </p>
      <div className={estilos.cuerpo}>
        <div className={estilos.cifras}>
          <Cifra
            etiqueta="Ciclo completo, promedio"
            valor={horas_o_guion(ciclo.promedio_horas_cerradas)}
            contexto={`${formatear_entero(ciclo.cuentas_cerradas)} cuentas cerradas`}
          />
          <Cifra
            etiqueta="Ciclo completo, mediana"
            valor={horas_o_guion(ciclo.mediana_horas_cerradas)}
            contexto={`${formatear_entero(ciclo.cuentas_cerradas)} cuentas cerradas`}
          />
          <Cifra
            etiqueta="Cuentas abiertas, antigüedad promedio"
            valor={horas_o_guion(ciclo.promedio_horas_abiertas)}
            contexto={contexto_abiertas(indicadores)}
          />
        </div>
        <div className={estilos.tabla}>
          <h3 className={estilos.titulo_tabla}>Cuentas abiertas más antiguas</h3>
          <TablaDatos
            columnas={_COLUMNAS}
            filas={ciclo.mas_antiguas_abiertas}
            obtener_clave={(fila) => fila.cuenta_medica_id}
            mensaje_vacio="No hay cuentas abiertas con este filtro."
            al_hacer_clic_fila={(fila) => void navegar(`/cuentas/${fila.cuenta_medica_id}`)}
          />
        </div>
      </div>
    </section>
  );
}
