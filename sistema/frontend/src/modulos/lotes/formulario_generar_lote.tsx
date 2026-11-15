import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { CamposGenerarLote } from "./campos_generar_lote";
import { SelectorCuentasElegibles } from "./selector_cuentas_elegibles";
import type { usar_formulario_generar_lote } from "./usar_formulario_generar_lote";
import estilos from "./dialogo_generar_lote.module.css";

interface Propiedades {
  formulario: ReturnType<typeof usar_formulario_generar_lote>;
  generando: boolean;
  error: unknown;
  al_generar: () => void;
  al_cerrar: () => void;
}

function falta_completar(formulario: ReturnType<typeof usar_formulario_generar_lote>): boolean {
  return !formulario.iafas_id || !formulario.periodo || formulario.cuenta_ids.length === 0;
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
      acciones={
        <>
          <Boton variante="secundario" onClick={al_cerrar}>
            Cancelar
          </Boton>
          <Boton
            variante="primario"
            onClick={al_generar}
            disabled={generando || falta_completar(formulario)}
          >
            Generar
          </Boton>
        </>
      }
    >
      <div className={estilos.formulario}>
        <MensajeErrorMutacion error={error} texto_por_defecto="No se pudo generar el lote." />
        <CamposGenerarLote
          iafas={formulario.consulta_iafas.data ?? []}
          iafas_id={formulario.iafas_id}
          periodo={formulario.periodo}
          al_elegir_iafas={formulario.elegir_iafas}
          al_cambiar_periodo={formulario.set_periodo}
        />
        {formulario.iafas_elegida ? (
          <SelectorCuentasElegibles
            codigo_iafas={formulario.iafas_elegida.codigo}
            cuentas={formulario.cuentas_elegibles}
            cuenta_ids_elegidos={formulario.cuenta_ids}
            al_alternar={formulario.alternar_cuenta}
          />
        ) : null}
      </div>
    </Dialogo>
  );
}
