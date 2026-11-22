import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { buscar_cie10, type ResumenCie10 } from "../../api/cie10";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";
import estilos from "./campo_cie10.module.css";

const _LARGO_MINIMO_BUSQUEDA = 2;

interface Propiedades {
  // El codigo elegido de la lista; vacio mientras no se elija.
  value: string;
  onChange: (codigo: string) => void;
  // Lo escrito en la caja, para saber si quedo algo sin elegir.
  al_escribir?: (texto: string) => void;
  // Al registrar la cuenta es opcional; despues, en la cuenta, ya no.
  etiqueta?: string;
  obligatorio?: boolean;
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
  al_elegir: (resultado: ResumenCie10) => void;
}) {
  if (buscando) return <span className={estilos.buscando}>Buscando…</span>;
  if (resultados.length === 0) {
    return <div className={estilos.sin_resultados}>Sin coincidencias para "{texto_buscado}".</div>;
  }
  return (
    <ul className={estilos.lista} role="listbox">
      {resultados.map((r) => (
        <li key={r.codigo}>
          <button type="button" className={estilos.opcion} onClick={() => al_elegir(r)}>
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
// ("embarazo", "hipertension") o el codigo y elige de la lista. Solo vale lo
// elegido: volver a escribir limpia la eleccion (igual que el producto de
// farmacia).
export function CampoCie10({
  value,
  onChange,
  al_escribir,
  etiqueta = "Diagnóstico principal (CIE-10, opcional)",
  obligatorio,
}: Propiedades) {
  const [texto, set_texto] = useState(value);
  const [mostrar_lista, set_mostrar_lista] = useState(false);
  const texto_diferido = usar_valor_diferido(texto.trim());
  const busqueda_habilitada =
    !value && texto_diferido.length >= _LARGO_MINIMO_BUSQUEDA && mostrar_lista;

  const consulta = useQuery({
    queryKey: ["cie10", "buscar", texto_diferido],
    queryFn: () => buscar_cie10(texto_diferido),
    enabled: busqueda_habilitada,
  });

  function elegir(resultado: ResumenCie10) {
    set_texto(`${resultado.codigo} · ${resultado.descripcion}`);
    set_mostrar_lista(false);
    onChange(resultado.codigo);
  }

  return (
    <div className={estilos.contenedor}>
      <CampoTexto
        etiqueta={etiqueta}
        obligatorio={obligatorio}
        value={texto}
        onChange={(evento) => {
          set_texto(evento.target.value);
          set_mostrar_lista(true);
          onChange("");
          al_escribir?.(evento.target.value);
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
