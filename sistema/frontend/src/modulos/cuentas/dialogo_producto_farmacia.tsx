import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  buscar_productos_catalogo,
  registrar_producto,
  type SolicitudProductoDispensado,
} from "../../api/farmacia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";

// RI-17 y CU-06: un producto dispensado, tomado del catalogo GTIN vigente,
// con los campos de la Tabla 4 del Anexo 1.
interface Formulario {
  codigo_producto: string;
  fecha_dispensacion: string;
  cantidad_venta: string;
  tipo_unidad_dispensacion: string;
  monto_unitario: string;
  copago: string;
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
    copago: "0",
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
    copago: f.copago || "0",
    monto_no_cubierto: f.monto_no_cubierto || "0",
    guia_farmacia: f.guia_farmacia.trim() || null,
  };
}

function SelectorProducto({ valor, al_cambiar }: { valor: string; al_cambiar: Cambiar }) {
  const [buscar, set_buscar] = useState("");
  const consulta = useQuery({
    queryKey: ["catalogo-gtin", "productos", buscar],
    queryFn: () => buscar_productos_catalogo(buscar),
    placeholderData: keepPreviousData,
  });
  const opciones = [
    { valor: "", etiqueta: "—" },
    ...(consulta.data ?? []).map((p) => ({
      valor: p.codigo,
      etiqueta: `${p.nombre} · ${p.denominacion_comun}${p.concentracion ? ` ${p.concentracion}` : ""} · ${p.codigo}`,
    })),
  ];
  return (
    <>
      <CampoTexto
        etiqueta="Buscar en el catálogo GTIN"
        value={buscar}
        onChange={(evento) => set_buscar(evento.target.value)}
      />
      <Selector
        etiqueta="Producto"
        opciones={opciones}
        value={valor}
        onChange={al_cambiar("codigo_producto")}
      />
    </>
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
        etiqueta="Copago (S/)"
        {...monto}
        value={formulario.copago}
        onChange={cambiar("copago")}
      />
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
      <SelectorProducto valor={formulario.codigo_producto} al_cambiar={cambiar} />
      <CamposProducto formulario={formulario} cambiar={cambiar} />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar el producto."
      />
    </Dialogo>
  );
}
