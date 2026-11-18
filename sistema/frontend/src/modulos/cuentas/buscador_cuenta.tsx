import { useState } from "react";
import type { ResumenCuenta } from "../../api/cuentas";
import { CampoTexto } from "../../componentes_base/campo_texto";
import estilos from "./campo_cie10.module.css";
import { usar_bandeja_cuentas } from "./usar_cuentas";

const _LARGO_MINIMO_BUSQUEDA = 2;
const _MAXIMO_RESULTADOS = 8;

function nombre_completo(cuenta: ResumenCuenta): string {
  return `${cuenta.nombres_asegurado} ${cuenta.apellidos_asegurado}`;
}

function coincide(cuenta: ResumenCuenta, texto: string): boolean {
  const buscado = texto.toLowerCase();
  return (
    cuenta.identificacion_interna.toLowerCase().includes(buscado) ||
    nombre_completo(cuenta).toLowerCase().includes(buscado)
  );
}

function ListaCuentas({
  cuentas,
  texto,
  al_elegir,
}: {
  cuentas: ResumenCuenta[];
  texto: string;
  al_elegir: (cuenta: ResumenCuenta) => void;
}) {
  if (cuentas.length === 0) {
    return <div className={estilos.sin_resultados}>Sin coincidencias para "{texto}".</div>;
  }
  return (
    <ul className={estilos.lista} role="listbox">
      {cuentas.map((cuenta) => (
        <li key={cuenta.id}>
          <button type="button" className={estilos.opcion} onClick={() => al_elegir(cuenta)}>
            <span className={estilos.codigo}>{cuenta.identificacion_interna}</span>
            <span className={estilos.descripcion}>{nombre_completo(cuenta)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

interface Propiedades {
  // Solo las cuentas de esa IAFAS, cuando se conoce.
  iafas_codigo?: string;
  elegida: ResumenCuenta | null;
  al_elegir: (cuenta: ResumenCuenta | null) => void;
}

// Busca una cuenta por su codigo o por el nombre del asegurado y deja
// elegirla de la lista (2026-11-18): antes habia que saberse el codigo y
// escribirlo completo.
export function BuscadorCuenta({ iafas_codigo, elegida, al_elegir }: Propiedades) {
  const [texto, set_texto] = useState("");
  const consulta = usar_bandeja_cuentas({ iafas_codigo });
  const buscado = texto.trim();
  const cuentas =
    elegida === null && buscado.length >= _LARGO_MINIMO_BUSQUEDA
      ? (consulta.data ?? [])
          .filter((cuenta) => coincide(cuenta, buscado))
          .slice(0, _MAXIMO_RESULTADOS)
      : null;

  return (
    <div className={estilos.contenedor}>
      <CampoTexto
        etiqueta="Cuenta"
        value={elegida ? `${elegida.identificacion_interna} — ${nombre_completo(elegida)}` : texto}
        onChange={(evento) => {
          set_texto(elegida ? "" : evento.target.value);
          al_elegir(null);
        }}
        autoComplete="off"
      />
      {cuentas ? <ListaCuentas cuentas={cuentas} texto={buscado} al_elegir={al_elegir} /> : null}
    </div>
  );
}
