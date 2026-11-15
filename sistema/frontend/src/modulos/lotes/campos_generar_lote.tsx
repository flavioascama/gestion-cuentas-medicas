import { CampoTexto } from "../../componentes_base/campo_texto";
import { Selector } from "../../componentes_base/selector";
import type { ResumenIafas } from "../../api/iafas";

interface Propiedades {
  iafas: ResumenIafas[];
  iafas_id: string;
  periodo: string;
  al_elegir_iafas: (valor: string) => void;
  al_cambiar_periodo: (valor: string) => void;
}

export function CamposGenerarLote({
  iafas,
  iafas_id,
  periodo,
  al_elegir_iafas,
  al_cambiar_periodo,
}: Propiedades) {
  return (
    <>
      <Selector
        etiqueta="IAFAS"
        opciones={[
          { valor: "", etiqueta: "Seleccione una IAFAS" },
          ...iafas.map((i) => ({
            valor: String(i.id),
            etiqueta: `${i.codigo} — ${i.razon_social}`,
          })),
        ]}
        value={iafas_id}
        onChange={(evento) => al_elegir_iafas(evento.target.value)}
      />
      <CampoTexto
        etiqueta="Periodo (AAAAMM)"
        value={periodo}
        onChange={(evento) => al_cambiar_periodo(evento.target.value)}
        placeholder="202609"
        maxLength={6}
      />
    </>
  );
}
