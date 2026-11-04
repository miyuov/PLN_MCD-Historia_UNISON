"""Fase 1 full-text: extracción de programas en título y cuerpo.

Entrada
    data/interim/corpus_analisis.parquet (notas internas, 2003-2026)
    data/interim/cuerpos_full.parquet    (cuerpos descargados)

Salida
    data/interim/noticias_limpias_full.parquet (solo con --guardar)

Reglas
- Se extraen menciones del título y del cuerpo por separado con el mismo
  patrón taxonómico y el mismo catálogo canónico de la Fase 1.
- Una nota cuenta una vez por programa. Si el programa aparece en título y
  cuerpo, se conserva la mención del título y se marca "Título y cuerpo".
- Las notas sin cuerpo conservan sus menciones de título.
- Los enlaces externos y los archivos ya fueron excluidos en
  ``preparar_corpus.py``; aquí solo se trabaja con notas internas.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
from tqdm import tqdm

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "features"))
sys.path.insert(0, str(RAIZ / "src" / "data"))

from catalogo_programas import CATALOGO
from fase1_limpieza_entidades import AUTOR_DEFECTO, extraer_menciones

COLUMNAS_MENCION = [
    "Fecha_ISO",
    "Año",
    "Título",
    "Autor/Dependencia",
    "Enlace",
    "Mencion",
    "Nivel",
    "Grupo",
    "Programa",
    "Fuente_Mencion",
]


def cargar_corpus(ruta: Path) -> pd.DataFrame:
    """Carga el corpus depurado y normaliza las columnas de trabajo."""
    corpus = pd.read_parquet(ruta)
    corpus = corpus.dropna(subset=["Fecha_ISO"]).copy()
    corpus["Título"] = corpus["Título"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    corpus["Año"] = pd.to_numeric(corpus["Año"], errors="coerce").astype("Int64")
    corpus = corpus.dropna(subset=["Año"]).copy()
    corpus["Año"] = corpus["Año"].astype(int)
    corpus["Autor/Dependencia"] = AUTOR_DEFECTO
    return corpus


def cargar_cuerpos(ruta: Path) -> pd.DataFrame:
    """Carga solo los cuerpos válidos."""
    cuerpos = pd.read_parquet(ruta, columns=["Enlace", "ok", "cuerpo", "chars"])
    cuerpos = cuerpos[cuerpos["ok"] & cuerpos["cuerpo"].fillna("").str.len().gt(0)]
    return cuerpos.drop_duplicates(subset=["Enlace"], keep="last")


def extraer_en_lotes(
    df: pd.DataFrame,
    columna: str,
    fuente: str,
    tamano_lote: int = 2000,
) -> tuple[pd.DataFrame, pd.Series]:
    """Extrae menciones por lotes para no cargar todo el texto a la vez."""
    partes = []
    ruidos = []
    inicios = range(0, len(df), tamano_lote)
    for inicio in tqdm(
        inicios,
        desc=f"Extrayendo {fuente}",
        unit="lote",
        dynamic_ncols=True,
    ):
        lote = df.iloc[inicio : inicio + tamano_lote].copy()
        if columna != "Título":
            lote = lote.drop(columns=["Título"]).rename(columns={columna: "Título"})
        menciones, ruido = extraer_menciones(lote)
        if len(menciones):
            menciones["Fuente_Mencion"] = fuente
            partes.append(menciones)
        if len(ruido):
            ruidos.append(ruido)

    if not partes:
        return pd.DataFrame(columns=COLUMNAS_MENCION), pd.Series(dtype="int64")

    ruido_total = (
        pd.concat(ruidos).groupby(level=0).sum().sort_values(ascending=False)
        if ruidos
        else pd.Series(dtype="int64")
    )
    return pd.concat(partes, ignore_index=True), ruido_total


def unir_fuentes(titulo: pd.DataFrame, cuerpo: pd.DataFrame) -> pd.DataFrame:
    """Une título y cuerpo sin duplicar y marca el origen de cada mención."""
    if titulo.empty:
        return cuerpo.copy()
    if cuerpo.empty:
        return titulo.copy()

    unido = pd.concat([titulo, cuerpo], ignore_index=True)
    unido["_prioridad"] = unido["Fuente_Mencion"].map({"Título": 0, "Cuerpo": 1})
    unido = unido.sort_values(["Enlace", "Programa", "_prioridad"])

    fuentes = (
        unido.groupby(["Enlace", "Programa"])["Fuente_Mencion"]
        .nunique()
        .rename("_n_fuentes")
        .reset_index()
    )
    unico = unido.drop_duplicates(subset=["Enlace", "Programa"], keep="first").merge(
        fuentes, on=["Enlace", "Programa"], how="left"
    )
    unico["Fuente_Mencion"] = unico["Fuente_Mencion"].where(
        unico["_n_fuentes"] <= 1,
        unico["Fuente_Mencion"].map({"Título": "Título y cuerpo", "Cuerpo": "Cuerpo y Título"}),
    )
    return unico.drop(columns=["_prioridad", "_n_fuentes"])


def imprimir_resumen(
    corpus: pd.DataFrame,
    con_cuerpo: int,
    titulo: pd.DataFrame,
    cuerpo: pd.DataFrame,
    union: pd.DataFrame,
    ruido_cuerpo: pd.Series,
    top: int,
) -> None:
    notas_titulo = titulo["Enlace"].nunique()
    notas_cuerpo = cuerpo["Enlace"].nunique()
    notas_union = union["Enlace"].nunique()
    notas_ambos = len(set(titulo["Enlace"]) & set(cuerpo["Enlace"]))
    notas_solo_cuerpo = len(set(cuerpo["Enlace"]) - set(titulo["Enlace"]))

    print("=" * 82)
    print("PUNTO DE CONTROL 1 FULL-TEXT - TÍTULO + CUERPO")
    print("=" * 82)
    print(f"Notas del corpus              : {len(corpus):,}")
    print(
        f"Notas con cuerpo válido       : {con_cuerpo:,} ({con_cuerpo / len(corpus) * 100:.2f}%)"
    )
    print(f"Notas con programa (título)   : {notas_titulo:,}")
    print(f"Notas con programa (cuerpo)   : {notas_cuerpo:,}")
    print(
        f"Notas con programa (unión)    : {notas_union:,} ({notas_union / len(corpus) * 100:.2f}%)"
    )
    print(f"  en título y cuerpo          : {notas_ambos:,}")
    print(f"  solo por el cuerpo          : {notas_solo_cuerpo:,}")
    print(f"Menciones (título)            : {len(titulo):,}")
    print(f"Menciones (cuerpo)            : {len(cuerpo):,}")
    print(f"Menciones (unión)             : {len(union):,}")
    print(f"Programas observados          : {union['Programa'].nunique():,} de {len(CATALOGO)}")

    print("\n" + "-" * 82)
    print("DESGLOSE POR NIVEL (UNIÓN)")
    print("-" * 82)
    por_grupo = (
        union.groupby("Grupo")
        .agg(Programas=("Programa", "nunique"), Menciones=("Programa", "size"))
        .reset_index()
    )
    por_grupo["% de menciones"] = (por_grupo["Menciones"] / len(union) * 100).round(1)
    print(por_grupo.to_markdown(index=False))

    print("\n" + "-" * 82)
    print(f"TOP {top} DE PROGRAMAS (TÍTULO + CUERPO)")
    print("-" * 82)
    freq = (
        union.groupby(["Programa", "Nivel", "Grupo"], as_index=False)
        .agg(Notas=("Enlace", "nunique"))
        .sort_values(["Notas", "Programa"], ascending=[False, True])
        .reset_index(drop=True)
    )
    freq.insert(0, "#", range(1, len(freq) + 1))
    print(freq.head(top).to_markdown(index=False))

    print("\n" + "-" * 82)
    print("ORIGEN DE LAS MENCIONES")
    print("-" * 82)
    print(
        union["Fuente_Mencion"]
        .value_counts()
        .rename_axis("Fuente")
        .to_frame("Menciones")
        .to_markdown()
    )

    print("\n" + "-" * 82)
    print("TÍTULOS VACÍOS")
    print("-" * 82)
    vacios = corpus[~corpus["Titulo_Valido"]]
    vacios_con_cuerpo = vacios["Enlace"].isin(cuerpo["Enlace"]).sum()
    print(f"Notas con título vacío o '.': {len(vacios):,}")
    print(f"  con mención recuperada del cuerpo: {int(vacios_con_cuerpo):,}")
    print(f"  sin mención recuperada           : {int(len(vacios) - vacios_con_cuerpo):,}")

    if len(ruido_cuerpo):
        print("\n" + "-" * 82)
        print("RUIDO MÁS FRECUENTE EN CUERPOS (TOP 10)")
        print("-" * 82)
        print(ruido_cuerpo.head(10).to_frame("Menciones").to_markdown())

    print(
        "\n[Punto de Control 1 full-text] No se escribió nada en data/interim. "
        "La persistencia requiere --guardar."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 1 full-text - programas en título y cuerpo")
    parser.add_argument("--corpus", default="data/interim/corpus_analisis.parquet")
    parser.add_argument("--cuerpos", default="data/interim/cuerpos_full.parquet")
    parser.add_argument("--salida", default="data/interim/noticias_limpias_full.parquet")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--limite", type=int, default=0, help="0 = todo el corpus")
    parser.add_argument("--guardar", action="store_true")
    args = parser.parse_args()

    corpus = cargar_corpus(RAIZ / args.corpus)
    if args.limite:
        corpus = corpus.head(args.limite).copy()
    total_corpus = len(corpus)

    cuerpos = cargar_cuerpos(RAIZ / args.cuerpos)
    enlaces_con_cuerpo = set(cuerpos["Enlace"])
    corpus["Tiene_Cuerpo"] = corpus["Enlace"].isin(enlaces_con_cuerpo)
    corpus = corpus[corpus["Titulo_Valido"] | corpus["Tiene_Cuerpo"]].copy()
    con_cuerpo = corpus[corpus["Tiene_Cuerpo"]].merge(
        cuerpos[["Enlace", "cuerpo"]].drop_duplicates(subset=["Enlace"]),
        on="Enlace",
        how="inner",
    )

    print(
        f"Corpus cargado: {len(corpus):,} notas | cuerpos válidos: {len(cuerpos):,} | "
        f"excluidas por no tener título ni cuerpo: {total_corpus - len(corpus):,}"
    )

    titulo, _ = extraer_en_lotes(corpus, "Título", "Título")
    cuerpo, ruido_cuerpo = extraer_en_lotes(con_cuerpo, "cuerpo", "Cuerpo")
    union = unir_fuentes(titulo, cuerpo)

    # Se recupera el título original y la bandera de título válido.
    union = union.drop(columns=["Título"], errors="ignore").merge(
        corpus[["Enlace", "Título", "Titulo_Valido"]], on="Enlace", how="left"
    )
    union = (
        union[COLUMNAS_MENCION]
        .sort_values(["Año", "Fecha_ISO", "Programa"])
        .reset_index(drop=True)
    )

    imprimir_resumen(
        corpus,
        len(con_cuerpo),
        titulo,
        cuerpo,
        union,
        ruido_cuerpo,
        args.top,
    )

    if args.guardar:
        salida = RAIZ / args.salida
        salida.parent.mkdir(parents=True, exist_ok=True)
        union.to_parquet(salida, index=False, compression="zstd")
        print(f"\nGuardado en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
