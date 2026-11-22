import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  corregir_carta_garantia,
  obtener_carta_garantia,
  registrar_carta_garantia,
  type CartaGarantia,
} from "../../api/carta_garantia";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { formatear_fecha, formatear_monto } from "../../utilidades/formato";
import estilos from "./detalle_cuenta.module.css";

// RF-13 y CU-06: la carta de garantia de la IAFAS (numero, vigencia y
// monto). Su vigencia es la que vigila el aviso de vencimiento (Tabla 61).
// Se registra y se corrige en Registrada y Rechazada (igual que el servidor).
const _ESTADOS_CARTA = new Set(["REGISTRADA", "RECHAZADA"]);

interface Formulario {
  numero: string;
  vigente_desde: string;
  vigente_hasta: string;
  monto: string;
}

const _VACIO: Formulario = { numero: "", vigente_desde: "", vigente_hasta: "", monto: "" };

function formulario_completo(f: Formulario): boolean {
  return [f.numero, f.vigente_desde, f.vigente_hasta, f.monto].every((v) => v.trim() !== "");
}

type Cambiar = (clave: keyof Formulario) => (evento: { target: { value: string } }) => void;

function CamposCarta({ formulario, cambiar }: { formulario: Formulario; cambiar: Cambiar }) {
  return (
    <>
      <CampoTexto
        etiqueta="Número"
        obligatorio
        maxLength={30}
        value={formulario.numero}
        onChange={cambiar("numero")}
      />
      <CampoTexto
        etiqueta="Vigente desde"
        obligatorio
        type="date"
        value={formulario.vigente_desde}
        onChange={cambiar("vigente_desde")}
      />
      <CampoTexto
        etiqueta="Vigente hasta"
        obligatorio
        type="date"
        value={formulario.vigente_hasta}
        onChange={cambiar("vigente_hasta")}
      />
      <CampoTexto
        etiqueta="Monto (S/)"
        obligatorio
        type="number"
        min="0.01"
        step="0.01"
        value={formulario.monto}
        onChange={cambiar("monto")}
      />
    </>
  );
}

function inicial(carta: CartaGarantia | null): Formulario {
  if (!carta) return _VACIO;
  const { numero, vigente_desde, vigente_hasta } = carta;
  return { numero, vigente_desde, vigente_hasta, monto: String(carta.monto) };
}

function usar_guardar_carta(
  cuenta_id: number,
  carta: CartaGarantia | null,
  formulario: Formulario,
  al_cerrar: () => void,
) {
  const cliente_consultas = useQueryClient();
  return useMutation({
    mutationFn: () =>
      carta
        ? corregir_carta_garantia(cuenta_id, formulario)
        : registrar_carta_garantia(cuenta_id, formulario),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      await cliente_consultas.invalidateQueries({ queryKey: ["plazos"] });
      al_cerrar();
    },
  });
}

function DialogoCartaGarantia({
  cuenta_id,
  carta,
  al_cerrar,
}: {
  cuenta_id: number;
  // Con la carta ya registrada, el dialogo la corrige.
  carta: CartaGarantia | null;
  al_cerrar: () => void;
}) {
  const [formulario, set_formulario] = useState<Formulario>(() => inicial(carta));
  const mutacion = usar_guardar_carta(cuenta_id, carta, formulario, al_cerrar);
  const completo = formulario_completo(formulario);
  const cambiar: Cambiar = (clave) => (evento) =>
    set_formulario({ ...formulario, [clave]: evento.target.value });

  return (
    <Dialogo
      titulo="Carta de garantía"
      al_cerrar={al_cerrar}
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={() => mutacion.mutate()}
            disabled={!completo || mutacion.isPending}
          >
            {carta ? "Guardar corrección" : "Registrar"}
          </Boton>
        </>
      }
    >
      <CamposCarta formulario={formulario} cambiar={cambiar} />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto={`No se pudo ${carta ? "corregir" : "registrar"} la carta de garantía.`}
      />
    </Dialogo>
  );
}

function DatosCarta({ carta }: { carta: CartaGarantia }) {
  const datos = [
    { etiqueta: "Número", valor: carta.numero },
    {
      etiqueta: "Vigencia",
      valor: `${formatear_fecha(carta.vigente_desde)} al ${formatear_fecha(carta.vigente_hasta)}`,
    },
    { etiqueta: "Monto", valor: formatear_monto(carta.monto) },
  ];
  return (
    <div className={estilos.datos_en_linea}>
      {datos.map((dato) => (
        <div key={dato.etiqueta} className={estilos.campo_dato}>
          <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
          <span className={estilos.valor_dato}>{dato.valor}</span>
        </div>
      ))}
    </div>
  );
}

// Sin carta se registra; con ella, se corrige (en Registrada y Rechazada).
function texto_accion_carta(con_carta: boolean, analista: boolean, estado: string): string | null {
  if (!con_carta) return "Registrar carta de garantía";
  return analista && _ESTADOS_CARTA.has(estado) ? "Corregir" : null;
}

// Paso "Carta de garantia" de la linea de la cuenta.
export function ContenidoCartaGarantia({
  cuenta_id,
  estado,
}: {
  cuenta_id: number;
  estado: string;
}) {
  const { sesion } = usar_sesion();
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "carta-garantia"],
    queryFn: () => obtener_carta_garantia(cuenta_id),
  });
  const [registrar, set_registrar] = useState(false);

  const carta = consulta.data ?? null;
  const analista = Boolean(sesion?.roles.includes("analista"));
  const puede_registrar = analista && _ESTADOS_CARTA.has(estado);
  if (consulta.isPending || (!carta && !puede_registrar)) return null;
  const accion = texto_accion_carta(Boolean(carta), analista, estado);

  return (
    <>
      {carta ? <DatosCarta carta={carta} /> : null}
      {accion ? (
        <div className={estilos.fila_accion}>
          <Boton variante="secundario" onClick={() => set_registrar(true)}>
            {accion}
          </Boton>
        </div>
      ) : null}
      {registrar ? (
        <DialogoCartaGarantia
          cuenta_id={cuenta_id}
          carta={carta}
          al_cerrar={() => set_registrar(false)}
        />
      ) : null}
    </>
  );
}
