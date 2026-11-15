"""Motor de sugerencia CPMS (Seccion 8.2, puntos 4-7): TF-IDF combinando
n-gramas de caracteres y de palabra, similitud de coseno, reordenamiento
por similitud de conjunto de tokens, indice persistido en disco.

`dominio/cpms/puertos.py::MotorSugerenciaCpms` es el contrato; esta clase
es la unica implementacion, y la unica que puede importar scikit-learn
(Seccion 5.2: el dominio no la conoce).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.dominio.cpms.normalizacion import normalizar
from app.dominio.cpms.valores import CandidatoCpms, FiltrosSugerencia, ProcedimientoCpms
from app.infraestructura.cpms.configuracion_motor import ConfiguracionMotorCpms


def _similitud_conjunto_tokens(tokens_consulta: set[str], tokens_documento: set[str]) -> float:
    """Indice de Jaccard: |interseccion| / |union|. 0.0 si ambos conjuntos
    son vacios (ninguna palabra en comun posible)."""

    if not tokens_consulta or not tokens_documento:
        return 0.0
    interseccion = len(tokens_consulta & tokens_documento)
    union = len(tokens_consulta | tokens_documento)
    return interseccion / union


@dataclass(frozen=True, slots=True)
class _Indice:
    cpms_version_id: int
    cpms_version_etiqueta: str
    procedimientos: tuple[ProcedimientoCpms, ...]
    tokens_por_procedimiento: tuple[frozenset[str], ...]
    vectorizador_caracteres: TfidfVectorizer
    vectorizador_palabras: TfidfVectorizer
    matriz: sp.csr_matrix


class MotorSugerenciaCpmsTfidf:
    def __init__(self, indice: _Indice, configuracion: ConfiguracionMotorCpms) -> None:
        self._indice = indice
        self._configuracion = configuracion

    @property
    def cpms_version_id(self) -> int:
        return self._indice.cpms_version_id

    @property
    def cpms_version_etiqueta(self) -> str:
        return self._indice.cpms_version_etiqueta

    @classmethod
    def construir(
        cls,
        procedimientos: list[ProcedimientoCpms],
        cpms_version_id: int,
        cpms_version_etiqueta: str,
        configuracion: ConfiguracionMotorCpms,
    ) -> MotorSugerenciaCpmsTfidf:
        denominaciones_normalizadas = [normalizar(p.denominacion) for p in procedimientos]

        vectorizador_caracteres = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(
                configuracion.ngramas_caracteres_minimo,
                configuracion.ngramas_caracteres_maximo,
            ),
        )
        vectorizador_palabras = TfidfVectorizer(
            analyzer="word",
            ngram_range=(
                configuracion.ngramas_palabras_minimo,
                configuracion.ngramas_palabras_maximo,
            ),
        )
        matriz_caracteres = vectorizador_caracteres.fit_transform(denominaciones_normalizadas)
        matriz_palabras = vectorizador_palabras.fit_transform(denominaciones_normalizadas)
        matriz = sp.hstack([matriz_caracteres, matriz_palabras], format="csr")

        tokens_por_procedimiento = tuple(
            frozenset(denominacion.split()) for denominacion in denominaciones_normalizadas
        )

        indice = _Indice(
            cpms_version_id=cpms_version_id,
            cpms_version_etiqueta=cpms_version_etiqueta,
            procedimientos=tuple(procedimientos),
            tokens_por_procedimiento=tokens_por_procedimiento,
            vectorizador_caracteres=vectorizador_caracteres,
            vectorizador_palabras=vectorizador_palabras,
            matriz=matriz,
        )
        return cls(indice, configuracion)

    def guardar(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._indice, ruta)

    @classmethod
    def cargar(
        cls, ruta: Path, configuracion: ConfiguracionMotorCpms
    ) -> MotorSugerenciaCpmsTfidf | None:
        if not ruta.exists():
            return None
        indice: _Indice = joblib.load(ruta)
        return cls(indice, configuracion)

    def _indices_tras_filtro(self, filtros: FiltrosSugerencia) -> list[int]:
        if (
            filtros.codigo_grupo is None
            and filtros.codigo_seccion is None
            and filtros.codigo_subseccion is None
        ):
            return list(range(len(self._indice.procedimientos)))
        return [
            i
            for i, p in enumerate(self._indice.procedimientos)
            if (filtros.codigo_grupo is None or p.codigo_grupo == filtros.codigo_grupo)
            and (filtros.codigo_seccion is None or p.codigo_seccion == filtros.codigo_seccion)
            and (
                filtros.codigo_subseccion is None
                or p.codigo_subseccion == filtros.codigo_subseccion
            )
        ]

    def sugerir(
        self, descripcion_normalizada: str, filtros: FiltrosSugerencia, maximo: int
    ) -> tuple[CandidatoCpms, ...]:
        indices_filtrados = self._indices_tras_filtro(filtros)
        if not indices_filtrados:
            return ()

        similitudes_lexicas = self._similitudes_lexicas(descripcion_normalizada, indices_filtrados)
        mejores = self._mejores_candidatos(
            descripcion_normalizada, indices_filtrados, similitudes_lexicas, maximo
        )
        return self._construir_candidatos(mejores)

    def _similitudes_lexicas(
        self, descripcion_normalizada: str, indices_filtrados: list[int]
    ) -> np.ndarray:
        vector_caracteres = self._indice.vectorizador_caracteres.transform(
            [descripcion_normalizada]
        )
        vector_palabras = self._indice.vectorizador_palabras.transform([descripcion_normalizada])
        vector_consulta = sp.hstack([vector_caracteres, vector_palabras], format="csr")
        submatriz = self._indice.matriz[indices_filtrados]
        similitudes: np.ndarray = cosine_similarity(vector_consulta, submatriz)[0]
        return similitudes

    def _mejores_candidatos(
        self,
        descripcion_normalizada: str,
        indices_filtrados: list[int],
        similitudes_lexicas: np.ndarray,
        maximo: int,
    ) -> list[tuple[int, float]]:
        cantidad_recuperada = min(
            self._configuracion.candidatos_recuperados, len(indices_filtrados)
        )
        orden_lexico = np.argsort(-similitudes_lexicas)[:cantidad_recuperada]

        tokens_consulta = set(descripcion_normalizada.split())
        puntuados: list[tuple[int, float]] = []
        for posicion_local in orden_lexico:
            indice_global = indices_filtrados[posicion_local]
            similitud_lexica = float(similitudes_lexicas[posicion_local])
            similitud_tokens = _similitud_conjunto_tokens(
                tokens_consulta, self._indice.tokens_por_procedimiento[indice_global]
            )
            puntaje_final = (
                self._configuracion.peso_similitud_lexica * similitud_lexica
                + self._configuracion.peso_similitud_tokens * similitud_tokens
            )
            puntuados.append((indice_global, puntaje_final))

        puntuados.sort(key=lambda par: par[1], reverse=True)
        return puntuados[: min(maximo, self._configuracion.candidatos_devueltos)]

    def _construir_candidatos(self, mejores: list[tuple[int, float]]) -> tuple[CandidatoCpms, ...]:
        candidatos = []
        for posicion, (indice_global, puntaje) in enumerate(mejores, start=1):
            procedimiento = self._indice.procedimientos[indice_global]
            candidatos.append(
                CandidatoCpms(
                    codigo=procedimiento.codigo,
                    denominacion=procedimiento.denominacion,
                    codigo_grupo=procedimiento.codigo_grupo,
                    nombre_grupo=procedimiento.nombre_grupo,
                    codigo_seccion=procedimiento.codigo_seccion,
                    nombre_seccion=procedimiento.nombre_seccion,
                    codigo_subseccion=procedimiento.codigo_subseccion,
                    nombre_subseccion=procedimiento.nombre_subseccion,
                    puntaje=puntaje,
                    posicion=posicion,
                )
            )
        return tuple(candidatos)
