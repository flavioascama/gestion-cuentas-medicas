import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  buscar_productos_catalogo,
  type ProductoCatalogo,
  registrar_producto,
  type SolicitudProductoDispensado,
} from "../../api/farmacia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";
import { usar_valor_diferido } from "../../utilidades/usar_valor_diferido";
import estilos_campo from "./campo_cie10.module.css";

// RI-17 y CU-06: un producto dispensado, tomado del catalogo GTIN vigente,
// con los campos de la Tabla 4 del Anexo 1. El copago no se pide: sale de
// la acreditacion del asegurado (2026-11-18).
interface Formulario {
  codigo_producto: string;
  fecha_dispensacion: string;
  cantidad_venta: string;
  tipo_unidad_dispensacion: string;
  monto_unitario: string;
  monto_no_cubierto: string;
  exento_igv: string;
  guia_farmacia: string;
}

type Cambiar = (clave: keyof Formulario) => (evento: { target: { value: string } }) => void;

const _UNIDADES = [
  { valor: "1", etiqueta: "Por empaque" },
  { valor: "2", etiqueta: "Por fracción" },
];
const _IGV = [
  { valor: "A", etiqueta: "No exonerado" },
  { valor: "D", etiqueta: "Exonerado" },
];

function inicial(fecha_prestacion: string): Formulario {
  return {
    codigo_producto: "",
    fecha_dispensacion: fecha_prestacion,
    cantidad_venta: "",
    tipo_unidad_dispensacion: "1",
    monto_unitario: "",
    monto_no_cubierto: "0",
    exento_igv: "A",
    guia_farmacia: "",
  };
}

function completo(f: Formulario): boolean {
  return [f.codigo_producto, f.fecha_dispensacion, f.cantidad_venta, f.monto_unitario].every(
    (valor) => valor.trim() !== "",
  );
}

function a_solicitud(f: Formulario): SolicitudProductoDispensado {
  return {
    ...f,
    monto_no_cubierto: f.monto_no_cubierto || "0",
    guia_farmacia: f.guia_farmacia.trim() || null,
  };
}

function ListaProductos({
  productos,
  buscando,
  al_elegir,
}: {
  productos: ProductoCatalogo[];
  buscando: boolean;
  al_elegir: (producto: ProductoCatalogo) => void;
}) {
  if (buscando) return <span className={estilos_campo.buscando}>Buscando…</span>;
  if (productos.length === 0)
    return <div className={estilos_campo.sin_resultados}>Sin coincidencias.</div>;
  return (
    <ul className={estilos_campo.lista} role="listbox">
      {productos.map((p) => (
        <li key={p.codigo}>
          <button type="button" className={estilos_campo.opcion} onClick={() => al_elegir(p)}>
            <span className={estilos_campo.codigo}>{p.codigo}</span>
            <span className={estilos_campo.descripcion}>
              {p.nombre} · {p.denominacion_comun}
              {p.concentracion ? ` ${p.concentracion}` : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// Un solo control: se escribe, se elige de las coincidencias y el campo
// muestra el producto elegido. Volver a escribir limpia la seleccion.
function SelectorProducto({ valor, al_elegir }: { valor: string; al_elegir: (c: string) => void }) {
  const [texto, set_texto] = useState("");
  const [mostrar_lista, set_mostrar_lista] = useState(false);
  const texto_diferido = usar_valor_diferido(texto.trim());
  const habilitada = !valor && mostrar_lista && texto_diferido.length >= 2;
  const consulta = useQuery({
    queryKey: ["catalogo-gtin", "productos", texto_diferido],
    queryFn: () => buscar_productos_catalogo(texto_diferido),
    enabled: habilitada,
  });
  function elegir(producto: ProductoCatalogo) {
    set_texto(`${producto.codigo} · ${producto.nombre}`);
    set_mostrar_lista(false);
    al_elegir(producto.codigo);
  }
  return (
    <div className={estilos_campo.contenedor}>
      <CampoTexto
        etiqueta="Producto (catálogo GTIN)"
        value={texto}
        onChange={(evento) => {
          set_texto(evento.target.value);
          set_mostrar_lista(true);
          al_elegir("");
        }}
        onFocus={() => set_mostrar_lista(true)}
        onBlur={() => setTimeout(() => set_mostrar_lista(false), 150)}
        autoComplete="off"
      />
      {habilitada ? (
        <ListaProductos
          productos={consulta.data ?? []}
          buscando={consulta.isFetching}
          al_elegir={elegir}
        />
      ) : null}
    </div>
  );
}

function CamposProducto({ formulario, cambiar }: { formulario: Formulario; cambiar: Cambiar }) {
  const monto = { type: "number", min: "0", step: "0.01" } as const;
  return (
    <>
      <CampoTexto
        etiqueta="Fecha de dispensación"
        type="date"
        value={formulario.fecha_dispensacion}
        onChange={cambiar("fecha_dispensacion")}
      />
      <CampoTexto
        etiqueta="Cantidad"
        {...monto}
        value={formulario.cantidad_venta}
        onChange={cambiar("cantidad_venta")}
      />
      <Selector
        etiqueta="Unidad de dispensación"
        opciones={_UNIDADES}
        value={formulario.tipo_unidad_dispensacion}
        onChange={cambiar("tipo_unidad_dispensacion")}
      />
      <CampoTexto
        etiqueta="Monto unitario sin IGV (S/)"
        {...monto}
        value={formulario.monto_unitario}
        onChange={cambiar("monto_unitario")}
      />
      <CamposMontosAdicionales formulario={formulario} cambiar={cambiar} />
    </>
  );
}

function CamposMontosAdicionales({
  formulario,
  cambiar,
}: {
  formulario: Formulario;
  cambiar: Cambiar;
}) {
  const monto = { type: "number", min: "0", step: "0.01" } as const;
  return (
    <>
      <CampoTexto
        etiqueta="Monto no cubierto (S/)"
        {...monto}
        value={formulario.monto_no_cubierto}
        onChange={cambiar("monto_no_cubierto")}
      />
      <Selector
        etiqueta="IGV"
        opciones={_IGV}
        value={formulario.exento_igv}
        onChange={cambiar("exento_igv")}
      />
      <CampoTexto
        etiqueta="Guía de farmacia"
        maxLength={12}
        value={formulario.guia_farmacia}
        onChange={cambiar("guia_farmacia")}
      />
    </>
  );
}

interface Propiedades {
  cuenta_id: number;
  fecha_prestacion: string;
  al_cerrar: () => void;
}

export function DialogoProductoFarmacia({ cuenta_id, fecha_prestacion, al_cerrar }: Propiedades) {
  const cliente_consultas = useQueryClient();
  const [formulario, set_formulario] = useState(() => inicial(fecha_prestacion));
  const mutacion = useMutation({
    mutationFn: () => registrar_producto(cuenta_id, a_solicitud(formulario)),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_cerrar();
    },
  });
  const cambiar: Cambiar = (clave) => (evento) =>
    set_formulario({ ...formulario, [clave]: evento.target.value });

  return (
    <Dialogo
      titulo="Producto de farmacia"
      al_cerrar={al_cerrar}
      ancho="grande"
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={!completo(formulario) || mutacion.isPending}
          >
            Registrar
          </Boton>
        </>
      }
    >
      <SelectorProducto
        valor={formulario.codigo_producto}
        al_elegir={(codigo) => set_formulario({ ...formulario, codigo_producto: codigo })}
      />
      <CamposProducto formulario={formulario} cambiar={cambiar} />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar el producto."
      />
    </Dialogo>
  );
}
