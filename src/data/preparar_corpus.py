"""Prepara el corpus analizable a partir del histórico crudo.

Criterios
- Solo notas internas con el patrón /nota/?idnoti=.
- Ventana temporal 2003-2026.
- Se conservan títulos vacíos si el enlace es una nota interna: se revisan
  después de descargar el cuerpo. Los enlaces a archivos y dominios externos
  quedan fuera del corpus.
- Se deduplica por Enlace.

Entrada : data/raw/noticias_raw_full.parquet
Salida  : data/interim/corpus_analisis.parquet
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA = RAIZ / "data/raw/noticias_raw_full.parquet"
SALIDA = RAIZ / "data/interim/corpus_analisis.parquet"

PATRON_NOTA = r"^https?://(?:www\.)?unison\.mx/nota/\?idnoti=\d+"
ANIO_MIN, ANIO_MAX = 2003, 2026


def main() -> None:
    raw = pd.read_parquet(ENTRADA)
    total = len(raw)

    enlace = raw["Enlace"].fillna("").astype(str)
    titulo = raw["Título"].fillna("").astype(str).str.strip()
    anio = pd.to_numeric(raw["Año"], errors="coerce")

    es_nota = enlace.str.match(PATRON_NOTA)
    en_ventana = anio.between(ANIO_MIN, ANIO_MAX)
    titulo_vacio = titulo.str.fullmatch(r"[.\s]*")

    excluidas_enlace = int((~es_nota).sum())
    excluidas_fecha = int((~en_ventana).sum())
    vacios_internos = int((es_nota & titulo_vacio).sum())
    duplicados = int(enlace.duplicated().sum())

    corpus = raw.loc[es_nota & en_ventana].copy()
    corpus["Título"] = corpus["Título"].fillna("").astype(str).str.strip()
    corpus["Titulo_Valido"] = ~corpus["Título"].str.fullmatch(r"[.\s]*")
    corpus = corpus.drop_duplicates(subset=["Enlace"], keep="first").reset_index(drop=True)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(SALIDA, index=False, compression="zstd")

    print("=" * 78)
    print("PREPARACIÓN DEL CORPUS ANALIZABLE")
    print("=" * 78)
    print(f"Filas de entrada                     : {total:,}")
    print(f"Excluidas por no ser nota interna    : {excluidas_enlace:,}")
    print(f"Excluidas por estar fuera de 2003-26 : {excluidas_fecha:,}")
    print(f"Duplicados de Enlace eliminados      : {duplicados:,}")
    print(f"Notas internas con título vacío/' .' : {vacios_internos:,}")
    print(f"Corpus analizable (Enlace único)     : {len(corpus):,}")
    print(f"  con título válido                  : {int(corpus['Titulo_Valido'].sum()):,}")
    print(f"  con título vacío (a revisar)       : {int((~corpus['Titulo_Valido']).sum()):,}")
    print(f"Guardado en                          : {SALIDA.relative_to(RAIZ)}")
    print("\nLas notas con título vacío se conservan para descargar su cuerpo;")
    print("si el cuerpo no trae texto, se excluirán del análisis final.")


if __name__ == "__main__":
    main()
