"""Fase 3 - Capa B+: categorías temáticas propuestas (TF-IDF + coseno).

Entrada
    data/interim/noticias_limpias_full.parquet
    data/interim/cuerpos_full.parquet

Salidas
    data/processed/categorias_notas.parquet
    data/processed/categorias_programas.parquet
    data/processed/categorias_definicion.parquet
    data/processed/resumen_pc2.parquet (columnas de categoría principal y top-3)

Decisiones metodológicas
- A diferencia de NMF, que descubre tópicos, esta capa compara cada nota contra
  una taxonomía fija de 19 categorías descritas con vocabulario controlado.
- La unidad es la nota: el cuerpo se vectoriza una sola vez y luego se une a
  las menciones. Así no se repite el cálculo por cada programa.
- Se usa el mismo TF-IDF del corpus para las notas y para las descripciones.
- Cada nota recibe su categoría principal y su top-3 por similitud coseno.
- Si la similitud máxima no alcanza 0.03, la nota se marca como
  `Otros / no clasificable`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "features"))

from taxonomia_categorias import (
    CATEGORIA_OTROS,
    CATEGORIAS,
    TOP_N,
    UMBRAL_SIMILITUD,
)

LARGO_TEXTO = 1500


def cargar_menciones(ruta: Path) -> pd.DataFrame:
    """Menciones de Fase 1 con tipos consistentes."""
    menciones = pd.read_parquet(ruta)
    menciones["Año"] = pd.to_numeric(menciones["Año"], errors="coerce").astype("Int64")
    return menciones.dropna(subset=["Año"]).copy()


def cargar_cuerpos(ruta: Path) -> pd.DataFrame:
    """Cuerpos válidos, sin duplicados por enlace."""
    cuerpos = pd.read_parquet(ruta, columns=["Enlace", "cuerpo"])
    cuerpos = cuerpos[cuerpos["cuerpo"].fillna("").str.len().gt(0)]
    return cuerpos.drop_duplicates(subset=["Enlace"], keep="last")


def construir_notas(menciones: pd.DataFrame, cuerpos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por nota con texto, para no repetir el cálculo por programa."""
    notas = (
        menciones[["Enlace"]]
        .drop_duplicates()
        .merge(cuerpos, on="Enlace", how="inner")
    )
    notas["Texto"] = notas["cuerpo"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    notas["Texto"] = notas["Texto"].str.slice(0, LARGO_TEXTO)
    return notas[notas["Texto"].str.len().gt(0)].reset_index(drop=True)


def vectorizar(textos: pd.Series) -> tuple[TfidfVectorizer, object]:
    """TF-IDF del corpus; se reutiliza para las descripciones de categorías."""
    vectorizador = TfidfVectorizer(
        token_pattern=r"(?u)\b[\wáéíóúñü]+\b",
        lowercase=True,
        sublinear_tf=True,
        min_df=5,
        max_df=0.6,
        max_features=30000,
    )
    return vectorizador, vectorizador.fit_transform(textos)


def clasificar_notas(
    notas: pd.DataFrame,
    vectorizador: TfidfVectorizer,
    matriz,
    n_top: int = TOP_N,
) -> pd.DataFrame:
    """Asigna categoría principal y top-n por similitud coseno."""
    nombres = list(CATEGORIAS)
    descripciones = vectorizador.transform([CATEGORIAS[nombre] for nombre in nombres])
    similitudes = cosine_similarity(matriz, descripciones)

    orden = np.argsort(-similitudes, axis=1)
    resultado = notas[["Enlace", "Texto"]].copy()
    for posicion in range(n_top):
        indices = orden[:, posicion]
        resultado[f"Categoria_{posicion + 1}"] = [nombres[i] for i in indices]
        resultado[f"Similitud_{posicion + 1}"] = similitudes[
            np.arange(len(resultado)), indices
        ].round(4)

    principal = resultado["Categoria_1"].where(
        resultado["Similitud_1"] >= UMBRAL_SIMILITUD, CATEGORIA_OTROS
    )
    resultado.insert(1, "Categoria", principal)
    resultado["Es_Otros"] = resultado["Categoria"] == CATEGORIA_OTROS
    return resultado


def categorias_por_programa(
    menciones: pd.DataFrame, notas: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Agrega la categoría de cada nota a las menciones de cada programa."""
    base = menciones[["Enlace", "Programa", "Nivel", "Grupo"]].merge(
        notas[["Enlace", "Categoria"]], on="Enlace", how="inner"
    )
    largo = (
        base.groupby(["Programa", "Nivel", "Grupo", "Categoria"], as_index=False)
        .agg(Menciones=("Enlace", "size"), Notas=("Enlace", "nunique"))
    )
    total = largo.groupby("Programa")["Menciones"].transform("sum")
    largo["Peso_Porcentaje"] = (largo["Menciones"] / total * 100).round(2)
    largo["Ranking"] = (
        largo.groupby("Programa")["Menciones"].rank(method="first", ascending=False).astype(int)
    )
    largo["Es_Top3"] = largo["Ranking"] <= TOP_N
    largo = largo.sort_values(["Programa", "Ranking"]).reset_index(drop=True)

    # Top-3 sin contar "Otros", para que el resumen hable de temas reales.
    reales = largo[largo["Categoria"] != CATEGORIA_OTROS]
    resumen = (
        reales.sort_values(["Programa", "Ranking"])
        .groupby("Programa")
        .head(TOP_N)
        .copy()
    )
    resumen["Posicion"] = resumen.groupby("Programa").cumcount() + 1
    ancho = resumen.pivot(
        index="Programa",
        columns="Posicion",
        values=["Categoria", "Peso_Porcentaje"],
    )
    ancho.columns = [f"{columna}_{posicion}" for columna, posicion in ancho.columns]
    ancho = ancho.reset_index()
    return largo, ancho


def definicion_categorias(notas: pd.DataFrame) -> pd.DataFrame:
    """Distribución global de categorías sobre las notas únicas."""
    total = len(notas)
    definicion = (
        notas["Categoria"]
        .value_counts()
        .rename_axis("Categoria")
        .reset_index(name="Notas")
    )
    definicion["Porcentaje"] = (definicion["Notas"] / total * 100).round(2)
    definicion["Descripcion"] = definicion["Categoria"].map(CATEGORIAS).fillna(
        "Notas sin similitud suficiente con ninguna categoría."
    )
    return definicion


def actualizar_resumen(ancho: pd.DataFrame) -> None:
    """Añade la categoría principal y el top-3 al resumen del PC2."""
    ruta = RAIZ / "data/processed/resumen_pc2.parquet"
    resumen = pd.read_parquet(ruta)
    columnas = {
        "Categoria_1": "Categoría Principal",
        "Peso_Porcentaje_1": "% Categoría Principal",
        "Categoria_2": "Categoría 2",
        "Peso_Porcentaje_2": "% Categoría 2",
        "Categoria_3": "Categoría 3",
        "Peso_Porcentaje_3": "% Categoría 3",
    }
    for origen, destino in columnas.items():
        if origen in ancho.columns:
            resumen[destino] = resumen["Programa"].map(ancho.set_index("Programa")[origen])
    resumen["Categoría Principal"] = resumen["Categoría Principal"].fillna(CATEGORIA_OTROS)
    resumen.to_parquet(ruta, index=False)


def imprimir_resumen(
    notas: pd.DataFrame,
    largo: pd.DataFrame,
    definicion: pd.DataFrame,
    top: int,
) -> None:
    print("=" * 82)
    print("FASE 3 - CAPA B+: CATEGORÍAS TEMÁTICAS PROPUESTAS")
    print("=" * 82)
    print("Modelo                : TF-IDF + similitud coseno")
    print(f"Categorías            : {len(CATEGORIAS)} + Otros")
    print(f"Umbral de asignación  : {UMBRAL_SIMILITUD}")
    print(f"Notas clasificadas    : {len(notas):,}")
    print(
        f"Notas con categoría   : {int((~notas['Es_Otros']).sum()):,} "
        f"({(~notas['Es_Otros']).mean() * 100:.1f}%)"
    )
    print(f"Programas con categoría: {largo['Programa'].nunique():,}")

    print("\n" + "-" * 82)
    print("DISTRIBUCIÓN GLOBAL")
    print("-" * 82)
    print(definicion[["Categoria", "Notas", "Porcentaje"]].to_markdown(index=False))

    print("\n" + "-" * 82)
    print(f"TOP {top} DE PROGRAMAS Y SU CATEGORÍA PRINCIPAL")
    print("-" * 82)
    principal = largo[largo["Ranking"] == 1].copy()
    principal = principal[principal["Categoria"] != CATEGORIA_OTROS]
    principal = principal.sort_values("Menciones", ascending=False).head(top)
    print(
        principal[
            ["Programa", "Grupo", "Categoria", "Peso_Porcentaje", "Menciones"]
        ].to_markdown(index=False)
    )

    print("\n" + "-" * 82)
    print("ARCHIVOS GENERADOS")
    print("-" * 82)
    print("  data/processed/categorias_notas.parquet")
    print("  data/processed/categorias_programas.parquet")
    print("  data/processed/categorias_definicion.parquet")
    print("  data/processed/resumen_pc2.parquet (columnas de categoría)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 3 - Categorías B+")
    parser.add_argument("--input", default="data/interim/noticias_limpias_full.parquet")
    parser.add_argument("--cuerpos", default="data/interim/cuerpos_full.parquet")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    menciones = cargar_menciones(RAIZ / args.input)
    cuerpos = cargar_cuerpos(RAIZ / args.cuerpos)
    notas = construir_notas(menciones, cuerpos)
    vectorizador, matriz = vectorizar(notas["Texto"])
    clasificadas = clasificar_notas(notas, vectorizador, matriz)
    clasificadas = clasificadas.drop(columns="Texto")

    largo, ancho = categorias_por_programa(menciones, clasificadas)
    definicion = definicion_categorias(clasificadas)

    salida = RAIZ / "data/processed"
    salida.mkdir(parents=True, exist_ok=True)
    clasificadas.to_parquet(salida / "categorias_notas.parquet", index=False)
    largo.to_parquet(salida / "categorias_programas.parquet", index=False)
    definicion.to_parquet(salida / "categorias_definicion.parquet", index=False)
    actualizar_resumen(ancho)

    imprimir_resumen(clasificadas, largo, definicion, args.top)


if __name__ == "__main__":
    main()
