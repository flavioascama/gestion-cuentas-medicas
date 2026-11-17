import { Boton } from "../../componentes_base/boton";
import { Dialogo } from "../../componentes_base/dialogo";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { MensajeVacio } from "../../componentes_base/mensaje_vacio";
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
  if (formulario.sugeridos.length === 0) {
    return <MensajeVacio texto="No hay cuentas facturadas por incluir en un lote." />;
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
