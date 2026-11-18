import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { reemplazar_comprobante, registrar_nota, type SolicitudNota } from "../../api/comprobante";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { Selector } from "../../componentes_base/selector";
import { MOTIVOS_NOTA, TIPOS_NOTA } from "./etiquetas_comprobante";

function usar_invalidar(cuenta_id: number, al_cerrar: () => void) {
  const cliente_consultas = useQueryClient();
  return async () => {
    await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
    al_cerrar();
  };
}

function Acciones(props: { al_cerrar: () => void; al_confirmar: () => void; habilitado: boolean }) {
  return (
    <>
      <Boton variante="secundario" onClick={props.al_cerrar}>
        Cancelar
      </Boton>
      <Boton variante="primario" onClick={props.al_confirmar} disabled={!props.habilitado}>
        Registrar
      </Boton>
    </>
  );
}

export function DialogoReemplazo({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const [motivo, set_motivo] = useState("");
  const mutacion = useMutation({
    mutationFn: () => reemplazar_comprobante(cuenta_id, motivo.trim()),
    onSuccess: usar_invalidar(cuenta_id, al_cerrar),
  });
  return (
    <Dialogo
      titulo="Comprobante de reemplazo"
      al_cerrar={al_cerrar}
      acciones={
        <Acciones
          al_cerrar={al_cerrar}
          al_confirmar={() => mutacion.mutate()}
          habilitado={motivo.trim() !== "" && !mutacion.isPending}
        />
      }
    >
      <CampoTexto
        etiqueta="Motivo"
        maxLength={300}
        value={motivo}
        onChange={(evento) => set_motivo(evento.target.value)}
      />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo emitir el reemplazo."
      />
    </Dialogo>
  );
}

// La serie, el numero y la fecha los da el PSE al emitirla (2026-11-18).
const _NOTA_VACIA: SolicitudNota = { tipo: "C", monto: "", motivo: "D" };

function a_opciones(mapa: Record<string, string>) {
  return Object.entries(mapa).map(([valor, etiqueta]) => ({ valor, etiqueta }));
}

function CamposNota(props: {
  nota: SolicitudNota;
  cambiar: (cambios: Partial<SolicitudNota>) => void;
}) {
  const { nota, cambiar } = props;
  return (
    <>
      <Selector
        etiqueta="Tipo"
        opciones={a_opciones(TIPOS_NOTA)}
        value={nota.tipo}
        onChange={(e) => cambiar({ tipo: e.target.value })}
      />
      <CampoTexto
        etiqueta="Monto sin IGV (S/)"
        type="number"
        min="0.01"
        step="0.01"
        value={String(nota.monto)}
        onChange={(e) => cambiar({ monto: e.target.value })}
      />
      <Selector
        etiqueta="Motivo"
        opciones={a_opciones(MOTIVOS_NOTA)}
        value={nota.motivo}
        onChange={(e) => cambiar({ motivo: e.target.value })}
      />
    </>
  );
}

export function DialogoNota({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const [nota, set_nota] = useState<SolicitudNota>(_NOTA_VACIA);
  const mutacion = useMutation({
    mutationFn: () => registrar_nota(cuenta_id, nota),
    onSuccess: usar_invalidar(cuenta_id, al_cerrar),
  });
  const completa = String(nota.monto) !== "";
  return (
    <Dialogo
      titulo="Nota de crédito o débito"
      al_cerrar={al_cerrar}
      acciones={
        <Acciones
          al_cerrar={al_cerrar}
          al_confirmar={() => mutacion.mutate()}
          habilitado={completa && !mutacion.isPending}
        />
      }
    >
      <CamposNota nota={nota} cambiar={(cambios) => set_nota({ ...nota, ...cambios })} />
      <MensajeErrorMutacion
        error={mutacion.error}
        texto_por_defecto="No se pudo registrar la nota."
      />
    </Dialogo>
  );
}
