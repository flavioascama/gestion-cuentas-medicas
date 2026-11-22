import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { useNavigate } from "react-router-dom";
import { marcar_aviso_atendido, type Aviso } from "../../api/avisos";
import { Boton } from "../../componentes_base/boton";
import { ControlSegmentado, type OpcionSegmento } from "../../componentes_base/control_segmentado";
import { IconoCampana } from "../../componentes_base/iconos_navegacion";
import { Mensaje } from "../../componentes_base/mensaje";
import { MensajeErrorMutacion } from "../../componentes_base/mensaje_error_mutacion";
import { MigasPan } from "../../componentes_base/migas_pan";
import { ConPaginacion } from "../../componentes_base/paginacion";
import { usar_pagina_cliente } from "../../componentes_base/paginar";
import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_ahora } from "../../utilidades/usar_ahora";
import { describir_aviso } from "./catalogo_avisos";
import { FilaAviso } from "./fila_aviso";
import { tipo_aviso } from "./severidad_avisos";
import { pendientes, recorrido_de_avisos, usar_avisos } from "./usar_avisos";
import estilos from "./bandeja_avisos.module.css";

// Bandeja de avisos (CU-08, CU-09, CU-11, CU-14, RNF-20), rediseñada el
// 2026-11-12: encabezado propio con icono (antes se confundia con la
// pantalla anterior), un aviso por hito en una fila entera clicable,
// pendientes separados de atendidos, y al abrir uno se puede volver o
// pasar al siguiente desde el detalle.

type Estado = "pendientes" | "atendidos" | "todos";
type Tipo = "todos" | "critico" | "escalamiento" | "aviso";

function contar(avisos: Aviso[], severidad: string): number {
  return avisos.filter((aviso) => tipo_aviso(aviso) === severidad).length;
}

function filtrar(avisos: Aviso[], estado: Estado, tipo: Tipo): Aviso[] {
  const por_estado =
    estado === "todos"
      ? avisos
      : avisos.filter((aviso) => aviso.atendido === (estado === "atendidos"));
  return tipo === "todos" ? por_estado : por_estado.filter((aviso) => tipo_aviso(aviso) === tipo);
}

function Encabezado() {
  return (
    <>
      <MigasPan migas={[{ etiqueta: "Inicio", ruta: "/" }, { etiqueta: "Avisos" }]} />
      <div className={estilos.encabezado}>
        <span className={estilos.icono_titulo}>
          <IconoCampana />
        </span>
        <h1 className={estilos.titulo}>Avisos</h1>
      </div>
    </>
  );
}

function Filtros({
  avisos,
  estado,
  tipo,
  al_cambiar,
}: {
  avisos: Aviso[];
  estado: Estado;
  tipo: Tipo;
  al_cambiar: (estado: Estado, tipo: Tipo) => void;
}) {
  const sin_atender = pendientes(avisos);
  const opciones_estado: OpcionSegmento<Estado>[] = [
    { valor: "pendientes", etiqueta: `Pendientes (${sin_atender.length})` },
    { valor: "atendidos", etiqueta: `Atendidos (${avisos.length - sin_atender.length})` },
    { valor: "todos", etiqueta: "Todos" },
  ];
  const base = filtrar(avisos, estado, "todos");
  const opciones_tipo: OpcionSegmento<Tipo>[] = [
    { valor: "todos", etiqueta: "Todos los tipos" },
    { valor: "critico", etiqueta: `Críticos (${contar(base, "critico")})` },
    { valor: "escalamiento", etiqueta: `Vencidos (${contar(base, "escalamiento")})` },
    { valor: "aviso", etiqueta: `Por vencer (${contar(base, "aviso")})` },
  ];
  return (
    <div className={estilos.filtros}>
      <ControlSegmentado
        opciones={opciones_estado}
        valor={estado}
        al_cambiar={(valor) => al_cambiar(valor, tipo)}
        etiqueta_accesible="Filtrar por atención"
      />
      <ControlSegmentado
        opciones={opciones_tipo}
        valor={tipo}
        al_cambiar={(valor) => al_cambiar(estado, valor)}
        etiqueta_accesible="Filtrar por tipo de aviso"
      />
    </div>
  );
}

// Para los avisos que nada resuelve solo: queda registrado quien lo marco.
function MarcarAtendido({ aviso }: { aviso: Aviso }) {
  const cliente_consultas = useQueryClient();
  const mutacion = useMutation({
    mutationFn: () => marcar_aviso_atendido(aviso.evento_id),
    onSuccess: () => void cliente_consultas.invalidateQueries({ queryKey: ["avisos"] }),
  });
  if (!aviso.marcable || aviso.atendido) return null;
  return (
    <div className={estilos.accion_aviso}>
      <Boton variante="terciario" onClick={() => mutacion.mutate()} disabled={mutacion.isPending}>
        Marcar como atendido
      </Boton>
      <MensajeErrorMutacion error={mutacion.error} texto_por_defecto="No se pudo marcar." />
    </div>
  );
}

function ListaAvisos({ avisos, al_abrir }: { avisos: Aviso[]; al_abrir: (aviso: Aviso) => void }) {
  const ahora = usar_ahora();
  const { pagina_actual, total_paginas, filas_pagina, set_pagina } = usar_pagina_cliente(avisos);
  if (avisos.length === 0) {
    return <p className={estilos.vacio}>No hay avisos con este filtro.</p>;
  }
  return (
    <>
      <ConPaginacion
        pagina={pagina_actual}
        total_paginas={total_paginas}
        total_registros={avisos.length}
        al_cambiar_pagina={set_pagina}
        etiqueta_entidad="avisos"
      >
        <div className={estilos.lista}>
          {filas_pagina.map((aviso) => (
            <Fragment key={aviso.evento_id}>
              <FilaAviso aviso={aviso} ahora={ahora} al_abrir={al_abrir} />
              <MarcarAtendido aviso={aviso} />
            </Fragment>
          ))}
        </div>
      </ConPaginacion>
    </>
  );
}

export function BandejaAvisos() {
  const navegar = useNavigate();
  const roles = usar_sesion().sesion?.roles ?? [];
  const consulta = usar_avisos(true);
  const [estado, set_estado] = useState<Estado>("pendientes");
  const [tipo, set_tipo] = useState<Tipo>("todos");
  const avisos = consulta.data ?? [];
  const visibles = filtrar(avisos, estado, tipo);

  const abrir = (aviso: Aviso) => {
    const destino = describir_aviso(aviso, roles).destino;
    if (destino)
      void navegar(destino, {
        state: { recorrido: recorrido_de_avisos(visibles, aviso, roles) },
      });
  };

  return (
    <div>
      <Encabezado />
      <Filtros
        avisos={avisos}
        estado={estado}
        tipo={tipo}
        al_cambiar={(nuevo_estado, nuevo_tipo) => {
          set_estado(nuevo_estado);
          set_tipo(nuevo_tipo);
        }}
      />
      {consulta.isError ? (
        <Mensaje tipo="error" texto="No se pudieron obtener los avisos." />
      ) : null}
      {consulta.isPending ? (
        <p className={estilos.vacio}>Cargando avisos…</p>
      ) : (
        <ListaAvisos key={`${estado}-${tipo}`} avisos={visibles} al_abrir={abrir} />
      )}
    </div>
  );
}
