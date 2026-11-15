import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
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
const _ESTADOS_SIN_REGISTRO = new Set(["CERRADA", "ANULADA"]);

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
        maxLength={30}
        value={formulario.numero}
        onChange={cambiar("numero")}
      />
      <CampoTexto
        etiqueta="Vigente desde"
        type="date"
        value={formulario.vigente_desde}
        onChange={cambiar("vigente_desde")}
      />
      <CampoTexto
        etiqueta="Vigente hasta"
        type="date"
        value={formulario.vigente_hasta}
        onChange={cambiar("vigente_hasta")}
      />
      <CampoTexto
        etiqueta="Monto (S/)"
        type="number"
        min="0.01"
        step="0.01"
        value={formulario.monto}
        onChange={cambiar("monto")}
      />
    </>
  );
}

function DialogoCartaGarantia({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [formulario, set_formulario] = useState<Formulario>(_VACIO);
  const mutacion = useMutation({
    mutationFn: () => registrar_carta_garantia(cuenta_id, formulario),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      await cliente_consultas.invalidateQueries({ queryKey: ["plazos"] });
      al_cerrar();
    },
  });
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
            Registrar
          </Boton>
        </>
      }
    >
      <CamposCarta formulario={formulario} cambiar={cambiar} />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar la carta de garantía."
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
    <div className={estilos.lista_compacta}>
      {datos.map((dato) => (
        <div key={dato.etiqueta} className={estilos.campo_dato}>
          <span className={estilos.etiqueta_dato}>{dato.etiqueta}</span>
          <span className={estilos.valor_dato}>{dato.valor}</span>
        </div>
      ))}
    </div>
  );
}

export function SeccionCartaGarantia({ cuenta_id, estado }: { cuenta_id: number; estado: string }) {
  const { sesion } = usar_sesion();
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "carta-garantia"],
    queryFn: () => obtener_carta_garantia(cuenta_id),
  });
  const [registrar, set_registrar] = useState(false);

  const carta = consulta.data ?? null;
  const puede_registrar =
    Boolean(sesion?.roles.includes("analista")) && !_ESTADOS_SIN_REGISTRO.has(estado);
  if (consulta.isPending || (!carta && !puede_registrar)) return null;

  return (
    <div className={estilos.seccion}>
      <div className={estilos.titulo_seccion}>Carta de garantía</div>
      {carta ? (
        <DatosCarta carta={carta} />
      ) : (
        <div className={estilos.fila_accion}>
          <Boton variante="secundario" onClick={() => set_registrar(true)}>
            Registrar carta de garantía
          </Boton>
        </div>
      )}
      {registrar ? (
        <DialogoCartaGarantia cuenta_id={cuenta_id} al_cerrar={() => set_registrar(false)} />
      ) : null}
    </div>
  );
}
