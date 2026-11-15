// Formatos de la administracion: cantidades con su unidad ("1 dia",
// "7 dias") en vez de numeros sueltos bajo un encabezado con la unidad.

export function con_unidad(valor: number | string, singular: string, plural: string): string {
  const numero = Number(valor);
  return `${valor} ${numero === 1 ? singular : plural}`;
}

// Miles separados por espacio, como los montos (GUIA_DISENO_INTERFAZ.md,
// Seccion 5): "12 002".
export function formatear_cantidad(valor: number): string {
  return String(valor).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}
