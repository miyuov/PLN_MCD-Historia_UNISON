"""Fase 2 - Skill 2: cuantificación de cobertura y brecha mediática.

Entrada
    data/interim/noticias_limpias.parquet (Fase 1 validada)
    data/raw/noticias_raw_full.parquet   (solo para normalizar por volumen)

Salidas
    data/processed/cobertura_programas.parquet
    data/processed/brecha_nivel.parquet
    data/processed/cobertura_anual.parquet
    data/processed/evolucion_nivel.parquet
    data/processed/olvido_mediatico.parquet
    data/processed/concentracion.parquet
    data/processed/resumen_pc2.parquet

Decisiones metodológicas
- Se usa pandas vectorizado. DuckDB no está instalado en el entorno y el
  volumen (1,403 menciones) no justifica una dependencia adicional.
- La cobertura institucional se calcula sobre las 37,985 notas del corpus,
  no sobre el subconjunto de 1,399. Así un programa con 101 notas tiene una
  cobertura de 0.27%, no de 7.2%.
- La evolución temporal se normaliza por las notas publicadas en cada periodo
  (menciones por 1,000 notas) para que un año con más noticias no parezca un
  año con más cobertura.
- El índice de olvido usa el cuartil inferior de la distribución de menciones
  sobre el catálogo completo (160 programas), incluidos los que tienen cero.
- 2026 es un año parcial (el corpus termina en octubre). Se marca en las
  salidas y no se usa para conclusiones de tendencia.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "features"))

from catalogo_programas import CATALOGO

GRUPO = {
    "Licenciatura": "Pregrado",
    "Ingeniería": "Pregrado",
    "Maestría": "Posgrado",
    "Doctorado": "Posgrado",
    "Especialidad": "Posgrado",
    "Posgrado": "Posgrado",
}

ANIO_PARCIAL = 2026
NIVEL_RE = r"^(Licenciatura|Ingeniería|Maestría|Doctorado|Especialidad|Posgrado)"


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def cargar_menciones(ruta: Path) -> pd.DataFrame:
    """Carga la Fase 1 y tipa las columnas temporales."""
    menciones = pd.read_parquet(ruta)
    menciones["Año"] = menciones["Año"].astype(int)
    menciones["Fecha_ISO"] = pd.to_datetime(menciones["Fecha_ISO"])
    return menciones


def totales_del_corpus(ruta: Path) -> tuple[pd.DataFrame, int]:
    """Notas publicadas por año en el corpus completo."""
    corpus = pd.read_parquet(ruta, columns=["Año"])
    corpus = corpus.dropna(subset=["Año"]).copy()
    corpus["Año"] = corpus["Año"].astype(int)
    totales = (
        corpus.groupby("Año", as_index=False).size().rename(columns={"size": "Notas_Periodo"})
    )
    return totales, len(corpus)


def catalogo_df() -> pd.DataFrame:
    """Catálogo canónico con Nivel y Grupo."""
    catalogo = pd.DataFrame({"Programa": CATALOGO}).drop_duplicates()
    catalogo["Nivel"] = catalogo["Programa"].str.extract(NIVEL_RE, expand=False)
    catalogo["Grupo"] = catalogo["Nivel"].map(GRUPO)
    return catalogo


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def cobertura_programas(
    menciones: pd.DataFrame, total_notas: int
) -> tuple[pd.DataFrame, float, float, float]:
    """Frecuencia, cobertura y categoría de olvido por programa."""
    notas_con_programa = menciones["Enlace"].nunique()

    freq = menciones.groupby(["Programa", "Nivel", "Grupo"], as_index=False).agg(
        Notas=("Enlace", "nunique"),
        Menciones=("Enlace", "size"),
        Primer_Año=("Año", "min"),
        Ultimo_Año=("Año", "max"),
        Años_Activo=("Año", "nunique"),
    )

    cobertura = catalogo_df().merge(freq, on=["Programa", "Nivel", "Grupo"], how="left")
    cobertura["Notas"] = cobertura["Notas"].fillna(0).astype(int)
    cobertura["Menciones"] = cobertura["Menciones"].fillna(0).astype(int)
    cobertura["Años_Activo"] = cobertura["Años_Activo"].fillna(0).astype(int)
    cobertura["Primer_Año"] = cobertura["Primer_Año"].astype("Int64")
    cobertura["Ultimo_Año"] = cobertura["Ultimo_Año"].astype("Int64")

    cobertura["Ranking"] = cobertura["Notas"].rank(method="min", ascending=False).astype(int)
    cobertura["% Cobertura institucional"] = (cobertura["Notas"] / total_notas * 100).round(3)
    cobertura["% del subconjunto"] = (cobertura["Notas"] / notas_con_programa * 100).round(2)
    cobertura["Notas por 1000"] = (cobertura["Notas"] / total_notas * 1000).round(3)

    q1, q2, q3 = cobertura["Notas"].quantile([0.25, 0.5, 0.75]).tolist()
    maximo = max(int(cobertura["Notas"].max()), 1)

    cobertura["Cuartil"] = np.select(
        [cobertura["Notas"] <= q1, cobertura["Notas"] <= q2, cobertura["Notas"] <= q3],
        ["Q1", "Q2", "Q3"],
        default="Q4",
    )
    cobertura["Categoria"] = np.select(
        [
            cobertura["Notas"] == 0,
            cobertura["Notas"] == 1,
            cobertura["Notas"] <= q2,
            cobertura["Notas"] <= q3,
        ],
        ["Sin mención", "Mención única", "Baja cobertura", "Cobertura media"],
        default="Alta cobertura",
    )
    cobertura["Es_Olvidado"] = cobertura["Notas"] <= q1
    cobertura["Indice_Olvido"] = (1 - cobertura["Notas"] / maximo).round(3)

    cobertura = cobertura.sort_values(["Notas", "Programa"], ascending=[False, True]).reset_index(
        drop=True
    )
    return cobertura, float(q1), float(q2), float(q3)


def brecha_nivel(
    menciones: pd.DataFrame, cobertura: pd.DataFrame, total_notas: int
) -> pd.DataFrame:
    """Volumen y cobertura por nivel académico."""
    por_grupo = menciones.groupby("Grupo", as_index=False).agg(
        Notas=("Enlace", "nunique"), Menciones=("Enlace", "size")
    )
    stats = cobertura.groupby("Grupo", as_index=False).agg(
        Programas=("Programa", "nunique"),
        Programas_Activos=("Notas", lambda notas: int((notas > 0).sum())),
        Menciones_por_Programa=("Notas", "sum"),
        Promedio_Notas_Catalogo=("Notas", "mean"),
        Mediana_Notas=("Notas", "median"),
        Maximo_Notas=("Notas", "max"),
    )
    stats["Promedio_Notas_Activos"] = stats["Menciones_por_Programa"] / stats["Programas_Activos"]
    brecha = por_grupo.merge(stats, on="Grupo", how="left")
    total_menciones = brecha["Menciones"].sum()
    total_programas = brecha["Programas"].sum()

    brecha["% Menciones"] = (brecha["Menciones"] / total_menciones * 100).round(2)
    brecha["% Cobertura institucional"] = (brecha["Notas"] / total_notas * 100).round(3)
    brecha["% del catálogo"] = (brecha["Programas"] / total_programas * 100).round(2)
    brecha["% Programas activos"] = (
        brecha["Programas_Activos"] / brecha["Programas"] * 100
    ).round(2)
    brecha["Promedio_Notas_Activos"] = brecha["Promedio_Notas_Activos"].round(2)
    brecha["Promedio_Notas_Catalogo"] = brecha["Promedio_Notas_Catalogo"].round(2)
    brecha["Mediana_Notas"] = brecha["Mediana_Notas"].round(2)
    return brecha.sort_values("Menciones", ascending=False).reset_index(drop=True)


def cobertura_anual(menciones: pd.DataFrame, totales: pd.DataFrame) -> pd.DataFrame:
    """Programa × año, normalizado por el volumen de notas del año."""
    anual = menciones.groupby(["Año", "Programa", "Nivel", "Grupo"], as_index=False).agg(
        Notas=("Enlace", "nunique")
    )
    anual = anual.merge(totales, on="Año", how="left")
    anual["% Cobertura anual"] = (anual["Notas"] / anual["Notas_Periodo"] * 100).round(3)
    anual["Notas por 1000"] = (anual["Notas"] / anual["Notas_Periodo"] * 1000).round(3)
    anual["Es_Anio_Parcial"] = anual["Año"] == ANIO_PARCIAL
    return anual.sort_values(["Año", "Notas", "Programa"], ascending=[True, False, True])


def _periodo(anios: pd.Series, tipo: str) -> pd.Series:
    """Etiqueta el periodo según el tipo solicitado."""
    if tipo == "Año":
        return anios.astype(str)
    if tipo == "Lustro":
        inicio = anios // 5 * 5
        return inicio.astype(str) + "-" + (inicio + 4).astype(str)
    decada = anios // 10 * 10
    return decada.astype(str) + "s"


def evolucion_nivel(menciones: pd.DataFrame, totales: pd.DataFrame) -> pd.DataFrame:
    """Evolución por nivel en año, lustro y década, normalizada por volumen."""
    bloques = []
    for tipo in ("Año", "Lustro", "Década"):
        base = menciones.copy()
        base["Periodo"] = _periodo(base["Año"], tipo)

        totales_periodo = totales.copy()
        totales_periodo["Periodo"] = _periodo(totales_periodo["Año"], tipo)
        totales_periodo = totales_periodo.groupby("Periodo", as_index=False)["Notas_Periodo"].sum()

        bloque = (
            base.groupby(["Periodo", "Grupo"], as_index=False)
            .agg(Notas=("Enlace", "nunique"), Menciones=("Enlace", "size"))
            .merge(totales_periodo, on="Periodo", how="left")
        )
        bloque["Periodo_Tipo"] = tipo
        bloque["% Cobertura"] = (bloque["Notas"] / bloque["Notas_Periodo"] * 100).round(3)
        bloque["Notas por 1000"] = (bloque["Notas"] / bloque["Notas_Periodo"] * 1000).round(3)
        if tipo == "Año":
            parcial = bloque["Periodo"] == str(ANIO_PARCIAL)
        elif tipo == "Década":
            parcial = bloque["Periodo"] == f"{ANIO_PARCIAL // 10 * 10}s"
        else:
            inicio = ANIO_PARCIAL // 5 * 5
            parcial = bloque["Periodo"] == f"{inicio}-{inicio + 4}"
        bloque["Es_Periodo_Parcial"] = parcial
        bloques.append(bloque)

    return pd.concat(bloques, ignore_index=True).sort_values(["Periodo_Tipo", "Periodo", "Grupo"])


def olvido_mediatico(cobertura: pd.DataFrame, q1: float) -> pd.DataFrame:
    """Programas en el cuartil inferior, incluidos los de cero menciones."""
    olvido = cobertura[cobertura["Notas"] <= q1].copy()
    olvido["Categoria_Olvido"] = np.select(
        [olvido["Notas"] == 0, olvido["Notas"] == 1],
        ["Sin mención", "Mención única"],
        default="Cobertura muy baja",
    )
    return olvido.sort_values(
        ["Notas", "Grupo", "Programa"], ascending=[True, True, True]
    ).reset_index(drop=True)


def concentracion(cobertura: pd.DataFrame) -> pd.DataFrame:
    """Participación del top-k, HHI y Gini de las menciones."""
    notas = cobertura["Notas"].to_numpy()
    total = notas.sum()
    ordenadas = np.sort(notas)
    n = len(ordenadas)
    shares = notas / total

    gini = (2 * np.arange(1, n + 1) * ordenadas).sum() / (n * ordenadas.sum()) - (n + 1) / n
    hhi = float((shares**2).sum() * 10000)

    filas = []
    for k in (1, 5, 10, 20, 50):
        participacion = shares[np.argsort(-notas)[:k]].sum() * 100
        filas.append((f"Participación Top {k}", round(float(participacion), 2)))
    filas.extend(
        [
            ("HHI (0-10,000)", round(hhi, 1)),
            ("Gini (0-1)", round(float(gini), 3)),
            ("Programas con al menos 1 mención", int((notas > 0).sum())),
            ("Programas con cero menciones", int((notas == 0).sum())),
        ]
    )
    return pd.DataFrame(filas, columns=["Metrica", "Valor"])


def resumen_pc2(cobertura: pd.DataFrame) -> pd.DataFrame:
    """Tabla del Punto de Control 2, ordenada por visibilidad."""
    resumen = cobertura[
        [
            "Ranking",
            "Programa",
            "Nivel",
            "Grupo",
            "Notas",
            "% Cobertura institucional",
            "% del subconjunto",
            "Categoria",
            "Cuartil",
            "Indice_Olvido",
            "Primer_Año",
            "Ultimo_Año",
            "Años_Activo",
        ]
    ].rename(
        columns={
            "Notas": "Total Menciones",
            "% Cobertura institucional": "% Cobertura Institucional",
            "% del subconjunto": "% del Subconjunto",
            "Indice_Olvido": "Índice de Olvido",
            "Primer_Año": "Primer Año",
            "Ultimo_Año": "Último Año",
            "Años_Activo": "Años Activo",
        }
    )
    resumen["Tópico Principal Asociado"] = "Pendiente (Fase 3)"
    return resumen


# ---------------------------------------------------------------------------
# Punto de Control 2
# ---------------------------------------------------------------------------
def imprimir_pc2(
    cobertura: pd.DataFrame,
    brecha: pd.DataFrame,
    olvido: pd.DataFrame,
    evolucion: pd.DataFrame,
    concentracion_df: pd.DataFrame,
    total_notas: int,
    notas_con_programa: int,
    total_menciones: int,
    q1: float,
    top: int,
) -> None:
    print("=" * 82)
    print("PUNTO DE CONTROL 2 - FASE 2: COBERTURA Y BRECHA MEDIÁTICA")
    print("=" * 82)
    print(f"Notas del corpus              : {total_notas:,}")
    print(
        f"Notas con al menos un programa: {notas_con_programa:,} "
        f"({notas_con_programa / total_notas * 100:.2f}%)"
    )
    print(f"Menciones catalogadas         : {total_menciones:,}")
    print(f"Programas del catálogo        : {len(cobertura):,}")
    print(f"Programas con al menos 1 nota : {int((cobertura['Notas'] > 0).sum()):,}")
    print(f"Umbral del cuartil inferior   : {q1:.0f} nota(s)")

    print("\n" + "-" * 82)
    print("BRECHA PREGRADO / POSGRADO")
    print("-" * 82)
    tabla_brecha = brecha[
        [
            "Grupo",
            "Programas",
            "Programas_Activos",
            "% del catálogo",
            "% Programas activos",
            "Notas",
            "% Cobertura institucional",
            "Menciones",
            "% Menciones",
            "Promedio_Notas_Activos",
            "Mediana_Notas",
            "Maximo_Notas",
        ]
    ].rename(
        columns={
            "% del catálogo": "% Catálogo",
            "% Programas activos": "% Activos",
            "% Cobertura institucional": "% Cobertura",
            "% Menciones": "% Menciones",
            "Promedio_Notas_Activos": "Promedio activo",
            "Mediana_Notas": "Mediana",
            "Maximo_Notas": "Máximo",
        }
    )
    print(tabla_brecha.to_markdown(index=False))

    pregrado = brecha.loc[brecha["Grupo"] == "Pregrado"].iloc[0]
    posgrado = brecha.loc[brecha["Grupo"] == "Posgrado"].iloc[0]
    print(
        f"\nBrecha de menciones: {pregrado['% Menciones'] - posgrado['% Menciones']:+.2f} "
        f"puntos porcentuales a favor de Pregrado."
    )
    print(
        f"Razón de cobertura: Pregrado tiene {pregrado['Notas'] / posgrado['Notas']:.2f} "
        f"notas por cada nota de Posgrado."
    )
    print(
        f"Promedio por programa activo: {pregrado['Promedio_Notas_Activos']:.1f} menciones "
        f"en Pregrado frente a {posgrado['Promedio_Notas_Activos']:.1f} en Posgrado."
    )

    print("\n" + "-" * 82)
    print(f"TOP {top} DE PROGRAMAS CON MAYOR COBERTURA")
    print("-" * 82)
    columnas_top = [
        "Ranking",
        "Programa",
        "Nivel",
        "Grupo",
        "Notas",
        "% Cobertura institucional",
        "% del subconjunto",
        "Categoria",
    ]
    print(cobertura.head(top)[columnas_top].to_markdown(index=False))

    print("\n" + "-" * 82)
    print("ÍNDICE DE OLVIDO MEDIÁTICO (CUARTIL INFERIOR)")
    print("-" * 82)
    conteo = olvido.groupby(["Grupo", "Categoria_Olvido"]).size().unstack(fill_value=0)
    print(conteo.to_string())
    print(
        f"\nTotal de programas olvidados: {len(olvido):,} de {len(cobertura):,} "
        f"({len(olvido) / len(cobertura) * 100:.1f}% del catálogo)."
    )
    print("\nProgramas sin ninguna mención (todos):")
    print(
        olvido[olvido["Notas"] == 0][
            ["Programa", "Nivel", "Grupo", "Notas", "Categoria_Olvido"]
        ].to_markdown(index=False)
    )
    print("\nCasos con mención única (muestra de 5):")
    print(
        olvido[olvido["Notas"] == 1].head(5)[
            ["Programa", "Nivel", "Grupo", "Notas", "Primer_Año", "Ultimo_Año"]
        ].to_markdown(index=False)
    )

    print("\n" + "-" * 82)
    print("EVOLUCIÓN POR DÉCADA (menciones por 1,000 notas)")
    print("-" * 82)
    decadas = evolucion[evolucion["Periodo_Tipo"] == "Década"].pivot(
        index="Periodo", columns="Grupo", values="Notas por 1000"
    )
    print(decadas.round(2).to_markdown())
    print(
        "\nNota: 2020s y el lustro 2025-2029 son periodos parciales; "
        "el corpus termina en octubre de 2026."
    )
    print("\nAño pico por nivel (solo años completos):")
    anual = evolucion[(evolucion["Periodo_Tipo"] == "Año") & (~evolucion["Es_Periodo_Parcial"])]
    for grupo in ("Pregrado", "Posgrado"):
        sub = anual[anual["Grupo"] == grupo]
        pico = sub.loc[sub["Notas por 1000"].idxmax()]
        print(
            f"  {grupo}: {pico['Periodo']} con {pico['Notas']:.0f} notas "
            f"({pico['Notas por 1000']:.2f} por 1,000)."
        )

    print("\n" + "-" * 82)
    print("CONCENTRACIÓN DE LA COBERTURA")
    print("-" * 82)
    print(concentracion_df.to_markdown(index=False))

    print("\n" + "-" * 82)
    print("ARCHIVOS GENERADOS")
    print("-" * 82)
    for nombre in (
        "cobertura_programas.parquet",
        "brecha_nivel.parquet",
        "cobertura_anual.parquet",
        "evolucion_nivel.parquet",
        "olvido_mediatico.parquet",
        "concentracion.parquet",
        "resumen_pc2.parquet",
    ):
        print(f"  data/processed/{nombre}")

    print(
        "\n[Punto de Control 2] Métricas guardadas. La Fase 3 (tópicos) "
        "requiere validación explícita."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 2 - Cobertura, brecha y olvido mediático")
    parser.add_argument(
        "--input",
        default="data/interim/noticias_limpias.parquet",
        help="Parquet limpio de la Fase 1.",
    )
    parser.add_argument(
        "--corpus",
        default="data/raw/noticias_raw_full.parquet",
        help="Corpus completo para normalizar por volumen.",
    )
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    menciones = cargar_menciones(RAIZ / args.input)
    totales, total_notas = totales_del_corpus(RAIZ / args.corpus)
    notas_con_programa = menciones["Enlace"].nunique()
    total_menciones = len(menciones)

    cobertura, q1, _, _ = cobertura_programas(menciones, total_notas)
    brecha = brecha_nivel(menciones, cobertura, total_notas)
    anual = cobertura_anual(menciones, totales)
    evolucion = evolucion_nivel(menciones, totales)
    olvido = olvido_mediatico(cobertura, q1)
    concentracion_df = concentracion(cobertura)
    resumen = resumen_pc2(cobertura)

    salida = RAIZ / "data/processed"
    salida.mkdir(parents=True, exist_ok=True)
    cobertura.to_parquet(salida / "cobertura_programas.parquet", index=False)
    brecha.to_parquet(salida / "brecha_nivel.parquet", index=False)
    anual.to_parquet(salida / "cobertura_anual.parquet", index=False)
    evolucion.to_parquet(salida / "evolucion_nivel.parquet", index=False)
    olvido.to_parquet(salida / "olvido_mediatico.parquet", index=False)
    concentracion_df.to_parquet(salida / "concentracion.parquet", index=False)
    resumen.to_parquet(salida / "resumen_pc2.parquet", index=False)

    imprimir_pc2(
        cobertura,
        brecha,
        olvido,
        evolucion,
        concentracion_df,
        total_notas,
        notas_con_programa,
        total_menciones,
        q1,
        args.top,
    )


if __name__ == "__main__":
    main()
