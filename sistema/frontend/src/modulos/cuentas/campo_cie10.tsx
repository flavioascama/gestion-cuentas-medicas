import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { buscar_cie10, type ResumenCie10 } from "../../api/cie10";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";
import estilos from "./campo_cie10.module.css";

const _LARGO_MINIMO_BUSQUEDA = 2;

interface Propiedades {
  value: string;
  onChange: (valor: string) => void;
}

function ListaResultadosCie10({
  resultados,
  texto_buscado,
  buscando,
  al_elegir,
}: {
  resultados: ResumenCie10[];
  texto_buscado: string;
  buscando: boolean;
  al_elegir: (codigo: string) => void;
}) {
  if (buscando) return <span className={estilos.buscando}>Buscando…</span>;
  if (resultados.length === 0) {
    return <div className={estilos.sin_resultados}>Sin coincidencias para "{texto_buscado}".</div>;
  }
  return (
    <ul className={estilos.lista} role="listbox">
      {resultados.map((r) => (
        <li key={r.codigo}>
          <button type="button" className={estilos.opcion} onClick={() => al_elegir(r.codigo)}>
            <span className={estilos.codigo}>{r.codigo}</span>
            <span className={estilos.descripcion}>{r.descripcion}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// Autocompletado del diagnostico CIE-10: el usuario no conoce los cerca de
// 13 mil codigos de memoria, asi que escribe la descripcion clinica
// ("embarazo", "hipertension") y elige de la lista -- sin dejar de admitir
// que alguien que ya conoce el codigo lo escriba directo, como antes.
export function CampoCie10({ value, onChange }: Propiedades) {
  const [mostrar_lista, set_mostrar_lista] = useState(false);
  const texto_diferido = usar_valor_diferido(value.trim());
  const busqueda_habilitada = texto_diferido.length >= _LARGO_MINIMO_BUSQUEDA && mostrar_lista;

  const consulta = useQuery({
    queryKey: ["cie10", "buscar", texto_diferido],
    queryFn: () => buscar_cie10(texto_diferido),
    enabled: busqueda_habilitada,
  });

  function elegir(codigo: string) {
    onChange(codigo);
    set_mostrar_lista(false);
  }

  return (
    <div className={estilos.contenedor}>
      <CampoTexto
        etiqueta="Diagnóstico principal (CIE-10, opcional)"
        value={value}
        onChange={(evento) => {
          onChange(evento.target.value);
          set_mostrar_lista(true);
        }}
        onFocus={() => set_mostrar_lista(true)}
        onBlur={() => setTimeout(() => set_mostrar_lista(false), 150)}
        maxLength={80}
        autoComplete="off"
      />
      {busqueda_habilitada ? (
        <ListaResultadosCie10
          resultados={consulta.data ?? []}
          texto_buscado={texto_diferido}
          buscando={consulta.isFetching}
          al_elegir={elegir}
        />
      ) : null}
    </div>
  );
}
