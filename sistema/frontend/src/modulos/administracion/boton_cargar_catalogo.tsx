import { useRef } from "react";
import { Boton } from "../../componentes_base/boton";

// "Cargar nueva versión" de un catálogo: abre el selector de archivos y
// entrega el Excel elegido.
export function BotonCargarCatalogo({
  al_elegir,
  disabled,
}: {
  al_elegir: (archivo: File) => void;
  disabled: boolean;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={entrada}
        type="file"
        accept=".xlsx"
        hidden
        onChange={(evento) => {
          const archivo = evento.target.files?.[0];
          evento.target.value = "";
          if (archivo) al_elegir(archivo);
        }}
      />
      <Boton variante="secundario" onClick={() => entrada.current?.click()} disabled={disabled}>
        Cargar nueva versión
      </Boton>
    </>
  );
}
