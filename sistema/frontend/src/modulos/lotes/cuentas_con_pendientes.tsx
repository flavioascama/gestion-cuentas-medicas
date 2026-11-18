import { Link } from "react-router-dom";
import estilos from "./dialogo_generar_lote.module.css";

// Cuentas que todavia no pueden entrar a un lote: de cual se trata, que le
// falta en palabras simples y el enlace para ir a completarlo (2026-11-18).
// Antes solo se veia la tabla, el campo y el criterio del estandar TEDEF.
export interface CuentaPendiente {
  cuenta_id: number;
  identificacion_interna: string;
  nombre?: string;
  pendientes: string[];
}

export function CuentasConPendientes({
  titulo,
  cuentas,
}: {
  titulo: string;
  cuentas: CuentaPendiente[];
}) {
  if (cuentas.length === 0) return null;
  return (
    <fieldset className={estilos.grupo}>
      <legend className={estilos.leyenda}>
        {titulo} ({cuentas.length})
      </legend>
      <ul className={estilos.lista_pendientes}>
        {cuentas.map((cuenta) => (
          <li key={cuenta.cuenta_id} className={estilos.fila_pendiente}>
            <span className={estilos.texto_largo}>
              {cuenta.identificacion_interna}
              {cuenta.nombre ? ` — ${cuenta.nombre}` : ""}
            </span>
            <span className={estilos.motivo_pendiente}>{cuenta.pendientes.join(" ")}</span>
            <Link to={`/cuentas/${cuenta.cuenta_id}`}>Abrir cuenta</Link>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}
