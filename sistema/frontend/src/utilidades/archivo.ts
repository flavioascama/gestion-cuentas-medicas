export async function leer_base64(archivo: File): Promise<string> {
  const bytes = new Uint8Array(await archivo.arrayBuffer());
  let binario = "";
  bytes.forEach((byte) => {
    binario += String.fromCharCode(byte);
  });
  return btoa(binario);
}

// Entrega al navegador un archivo descargado del servidor.
export function guardar_archivo(blob: Blob, nombre_archivo: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre_archivo;
  enlace.click();
  URL.revokeObjectURL(url);
}
