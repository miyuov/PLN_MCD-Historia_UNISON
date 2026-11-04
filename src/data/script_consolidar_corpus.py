"""Consolida lotes Parquet del corpus de noticias en un único archivo.

DuckDB es opcional: si está disponible se usa para leer los lotes sin cargarlos
completos en memoria; si no, se cae a pandas. El corpus definitivo ya está en
``data/raw/noticias_raw_full.parquet``; este script documenta cómo se consolidó
y permite reproducir el proceso si se vuelve a descargar por lotes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNAS = ["Fecha_ISO", "Título", "Enlace"]


def _consolidar_con_duckdb(rutas: list[str], salida: str) -> bool:
    """Intenta consolidar con DuckDB. Devuelve False si no está disponible o falla."""
    try:
        import duckdb
    except ImportError:
        return False

    consulta = f"""
    COPY (
        SELECT DISTINCT "Fecha_ISO", "Título", "Enlace"
        FROM read_parquet({rutas!r})
        WHERE "Fecha_ISO" IS NOT NULL
    ) TO '{salida}' (FORMAT PARQUET);
    """
    try:
        duckdb.sql(consulta)
    except duckdb.Error as exc:
        print(f"Error al consolidar con DuckDB: {exc}")
        return False
    return True


def consolidar_corpus(rutas_lotes: list[str | Path], output_path: str | Path) -> None:
    """Consolida varios Parquet, descarta filas sin fecha y deduplica."""
    print("Consolidando y limpiando el corpus...")
    salida = str(output_path)
    rutas = [str(ruta) for ruta in rutas_lotes]

    if _consolidar_con_duckdb(rutas, salida):
        print(f"Corpus consolidado exitosamente en: {salida}")
        return

    print("Usando fallback a Pandas...")
    dfs = [pd.read_parquet(ruta, columns=COLUMNAS) for ruta in rutas]
    df_final = pd.concat(dfs, ignore_index=True)
    df_final = df_final.dropna(subset=["Fecha_ISO"])
    df_final = df_final.drop_duplicates(subset=["Título", "Fecha_ISO"])
    df_final.to_parquet(output_path, index=False)
    print(f"Corpus consolidado con Pandas en: {salida}")


# Ejemplo de uso:
# consolidar_corpus(
#     ["data/raw/lote_*.parquet"], "data/interim/corpus_consolidado.parquet"
# )
