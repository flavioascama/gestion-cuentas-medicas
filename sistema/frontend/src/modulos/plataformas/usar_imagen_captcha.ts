import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { obtener_imagen_captcha } from "../../api/plataformas";

export function usar_imagen_captcha(sesion_id: number): string | null {
  const [url_imagen, set_url_imagen] = useState<string | null>(null);
  const consulta_imagen = useQuery({
    queryKey: ["plataformas", "captcha", sesion_id],
    queryFn: () => obtener_imagen_captcha(sesion_id),
  });

  useEffect(() => {
    if (!consulta_imagen.data) return;
    const url = URL.createObjectURL(consulta_imagen.data);
    set_url_imagen(url);
    return () => URL.revokeObjectURL(url);
  }, [consulta_imagen.data]);

  return url_imagen;
}
