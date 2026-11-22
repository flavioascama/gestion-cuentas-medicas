import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { registrar_copago_cobrado, type SolicitudCopagoCobrado } from "../../api/copago";
import { Boton } from "../../componentes_base/boton";
import { CampoTexto } from "../../componentes_base/campo_texto";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { fecha_local_hoy } from "../../utilidades/formato";

type Cobro = { monto: string; fecha: string; referencia: string };

function CamposCobro(props: { cobro: Cobro; cambiar: (cambios: Partial<Cobro>) => void }) {
  const { cobro, cambiar } = props;
  return (
    <>
      <CampoTexto
        etiqueta="Monto (S/)"
        obligatorio
        type="number"
        min="0.01"
        step="0.01"
        value={cobro.monto}
        onChange={(evento) => cambiar({ monto: evento.target.value })}
      />
      <CampoTexto
        etiqueta="Fecha del cobro"
        obligatorio
        type="date"
        max={fecha_local_hoy()}
        value={cobro.fecha}
        onChange={(evento) => cambiar({ fecha: evento.target.value })}
      />
      <CampoTexto
        etiqueta="Comprobante de caja"
        obligatorio
        maxLength={60}
        value={cobro.referencia}
        onChange={(evento) => cambiar({ referencia: evento.target.value })}
      />
    </>
  );
}

function DialogoCobroCopago({
  cuenta_id,
  al_cerrar,
}: {
  cuenta_id: number;
  al_cerrar: () => void;
}) {
  const cliente_consultas = useQueryClient();
  const [cobro, set_cobro] = useState<Cobro>({
    monto: "",
    fecha: fecha_local_hoy(),
    referencia: "",
  });
  const solicitud: SolicitudCopagoCobrado = { ...cobro, referencia: cobro.referencia.trim() };
  const mutacion = useMutation({
    mutationFn: () => registrar_copago_cobrado(cuenta_id, solicitud),
    onSuccess: async () => {
      await cliente_consultas.invalidateQueries({ queryKey: ["cuentas", cuenta_id] });
      al_cerrar();
    },
  });
  const completo = cobro.monto !== "" && cobro.fecha !== "" && solicitud.referencia !== "";
  return (
    <Dialogo
      titulo="Registrar cobro del copago"
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
      <CamposCobro cobro={cobro} cambiar={(cambios) => set_cobro({ ...cobro, ...cambios })} />
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo registrar." />
    </Dialogo>
  );
}

export function BotonRegistrarCobro({ cuenta_id }: { cuenta_id: number }) {
  const [abierto, set_abierto] = useState(false);
  return (
    <>
      <Boton variante="secundario" onClick={() => set_abierto(true)}>
        Registrar cobro
      </Boton>
      {abierto ? (
        <DialogoCobroCopago cuenta_id={cuenta_id} al_cerrar={() => set_abierto(false)} />
      ) : null}
    </>
  );
}
