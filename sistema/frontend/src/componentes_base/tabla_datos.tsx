import type { KeyboardEvent, ReactNode } from "react";
import { MensajeErrorMutacion } from "./mensaje_error_mutacion";
import { MensajeVacio } from "./mensaje_vacio";
import estilos from "./tabla_datos.module.css";

export interface ColumnaTabla<T> {
  clave: keyof T & string;
  encabezado: string;
  alinear_derecha?: boolean;
  alinear_centro?: boolean;
  formatear?: (fila: T) => ReactNode;
}

interface Propiedades<T> {
  columnas: ColumnaTabla<T>[];
  filas: T[];
  obtener_clave: (fila: T, indice: number) => string | number;
  cargando?: boolean;
  // Hay filas a la vista mientras llega una respuesta nueva (otro filtro).
  actualizando?: boolean;
  error?: unknown;
  mensaje_vacio?: string;
  al_hacer_clic_fila?: (fila: T) => void;
}

function formatear_valor(valor: unknown): ReactNode {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "boolean") return valor ? "Sí" : "No";
  if (typeof valor === "string" || typeof valor === "number") return valor;
  return JSON.stringify(valor);
}

function clase_alineacion<T>(columna: ColumnaTabla<T>): string | undefined {
  if (columna.alinear_centro) return estilos.alinear_centro;
  if (columna.alinear_derecha) return estilos.alinear_derecha;
  return undefined;
}

// Enter o Espacio abren la fila, igual que el clic. Solo si el foco esta
// en la fila misma, no en un control dentro de una celda.
function al_tecla_fila(evento: KeyboardEvent<HTMLTableRowElement>, abrir: () => void): void {
  if (evento.target !== evento.currentTarget) return;
  if (evento.key !== "Enter" && evento.key !== " ") return;
  evento.preventDefault();
  abrir();
}

function Encabezado<T>({ columnas }: { columnas: ColumnaTabla<T>[] }) {
  return (
    <thead>
      <tr>
        {columnas.map((columna, indice) => (
          <th key={`${columna.clave}-${indice}`} className={clase_alineacion(columna)}>
            {columna.encabezado}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function FilaDatos<T>({
  fila,
  columnas,
  clave,
  al_hacer_clic,
}: {
  fila: T;
  columnas: ColumnaTabla<T>[];
  clave: string | number;
  al_hacer_clic?: (fila: T) => void;
}) {
  return (
    <tr
      key={clave}
      className={al_hacer_clic ? estilos.fila_clicable : undefined}
      tabIndex={al_hacer_clic ? 0 : undefined}
      onClick={() => al_hacer_clic?.(fila)}
      onKeyDown={
        al_hacer_clic ? (evento) => al_tecla_fila(evento, () => al_hacer_clic(fila)) : undefined
      }
    >
      {columnas.map((columna, indice) => (
        <td key={`${columna.clave}-${indice}`} className={clase_alineacion(columna)}>
          {columna.formatear ? columna.formatear(fila) : formatear_valor(fila[columna.clave])}
        </td>
      ))}
    </tr>
  );
}

export function TablaDatos<T>({
  columnas,
  filas,
  obtener_clave,
  cargando = false,
  actualizando = false,
  error,
  mensaje_vacio = "No hay registros para mostrar.",
  al_hacer_clic_fila,
}: Propiedades<T>) {
  if (error) {
    return (
      <div className={estilos.envoltorio}>
        <MensajeErrorMutacion error={error} texto_por_defecto="No se pudieron cargar los datos." />
      </div>
    );
  }

  return (
    <div className={estilos.envoltorio}>
      <table className={`${estilos.tabla} ${actualizando ? estilos.actualizando : ""}`}>
        <Encabezado columnas={columnas} />
        <tbody>
          {cargando ? (
            <tr>
              <td colSpan={columnas.length}>Cargando…</td>
            </tr>
          ) : (
            filas.map((fila, indice) => (
              <FilaDatos
                key={obtener_clave(fila, indice)}
                fila={fila}
                columnas={columnas}
                clave={obtener_clave(fila, indice)}
                al_hacer_clic={al_hacer_clic_fila}
              />
            ))
          )}
        </tbody>
      </table>
      {!cargando && filas.length === 0 ? <MensajeVacio texto={mensaje_vacio} /> : null}
    </div>
  );
}
