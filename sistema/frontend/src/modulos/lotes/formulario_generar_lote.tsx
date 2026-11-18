import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { MensajeVacio } from "../../componentes_base/mensaje_vacio";
import { CuentasConPendientes } from "./cuentas_con_pendientes";
import { SelectorCuentasElegibles } from "./selector_cuentas_elegibles";
import { SelectorLotesSugeridos } from "./selector_lotes_sugeridos";
import type { usar_formulario_generar_lote } from "./usar_formulario_generar_lote";
import estilos from "./dialogo_generar_lote.module.css";

type Formulario = ReturnType<typeof usar_formulario_generar_lote>;

interface Propiedades {
  formulario: Formulario;
  generando: boolean;
  error: unknown;
  al_generar: () => void;
  al_cerrar: () => void;
}

function LotesSugeridos({ formulario }: { formulario: Formulario }) {
  if (formulario.consulta.isPending) return <MensajeVacio texto="Consultando las cuentas…" />;
  if (formulario.consulta.isError) {
    return <Mensaje tipo="error" texto="No se pudieron consultar las cuentas facturadas." />;
  }
  const pendientes = (
    <CuentasConPendientes
      titulo="Cuentas con datos pendientes"
      cuentas={formulario.con_pendientes.map((cuenta) => ({
        cuenta_id: cuenta.cuenta_id,
        identificacion_interna: cuenta.identificacion_interna,
        nombre: `${cuenta.nombres_asegurado} ${cuenta.apellidos_asegurado}`,
        pendientes: cuenta.pendientes ?? [],
      }))}
    />
  );
  if (formulario.sugeridos.length === 0) {
    return (
      <>
        <MensajeVacio texto="No hay cuentas listas para incluir en un lote." />
        {pendientes}
      </>
    );
  }
  return (
    <>
      <SelectorLotesSugeridos
        sugeridos={formulario.sugeridos}
        elegido={formulario.elegido}
        al_elegir={formulario.elegir}
      />
      {formulario.elegido ? (
        <SelectorCuentasElegibles
          cuentas={formulario.elegido.cuentas}
          excluidas={formulario.excluidas}
          al_alternar={formulario.alternar_cuenta}
          al_alternar_todas={formulario.alternar_todas}
        />
      ) : null}
      {pendientes}
    </>
  );
}

export function FormularioGenerarLote({
  formulario,
  generando,
  error,
  al_generar,
  al_cerrar,
}: Propiedades) {
  return (
    <Dialogo
      titulo="Generar lote"
      al_cerrar={al_cerrar}
      ancho="grande"
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={al_generar}
            disabled={generando || formulario.cuenta_ids.length === 0}
          >
            Generar
          </Boton>
        </>
      }
    >
      <div className={estilos.formulario}>
        <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo generar el lote." />
        <LotesSugeridos formulario={formulario} />
      </div>
    </Dialogo>
  );
}
