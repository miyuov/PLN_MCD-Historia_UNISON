"""Fase 4 - Figuras para la narrativa en tres actos.

Entrada
    data/processed/cobertura_programas.parquet
    data/processed/brecha_nivel.parquet
    data/processed/evolucion_nivel.parquet
    data/processed/olvido_mediatico.parquet
    data/processed/topicos_programas.parquet
    data/processed/topicos_nivel.parquet

Salida
    reports/figures/fig01_top20_cobertura.png
    reports/figures/fig02_brecha_nivel.png
    reports/figures/fig03_evolucion_nivel.png
    reports/figures/fig04_topicos_nivel.png
    reports/figures/fig05_topicos_top_programas.png
    reports/figures/fig06_olvido_mediatico.png
    reports/figures/fig07_categorias.png

Las figuras son la evidencia visual del reporte `reports/fase4_narrativa.md`.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PROCESADO = RAIZ / "data" / "processed"
FIGURAS = RAIZ / "reports" / "figures"

COLOR_PREGRADO = "#4c72b0"
COLOR_POSGRADO = "#dd8452"
COLOR_OLVIDO = "#c44e52"
COLOR_BAJA = "#e8a87c"

ANIO_PARCIAL = 2026


def _guardar(fig: plt.Figure, nombre: str) -> None:
    FIGURAS.mkdir(parents=True, exist_ok=True)
    ruta = FIGURAS / nombre
    fig.savefig(ruta, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[ok] {ruta.relative_to(RAIZ)}")


def fig_top20(cobertura: pd.DataFrame) -> None:
    top = cobertura.head(20).sort_values("Notas")
    colores = top["Grupo"].map({"Pregrado": COLOR_PREGRADO, "Posgrado": COLOR_POSGRADO})
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(top["Programa"], top["Notas"], color=colores)
    ax.set_xlabel("Notas que mencionan el programa")
    ax.set_title("Top 20 de programas por cobertura mediática (2003–2026)")
    ax.grid(axis="x", alpha=0.3)
    for y, valor in enumerate(top["Notas"]):
        ax.text(valor + 8, y, f"{valor:,}", va="center", fontsize=8)
    ax.set_xlim(0, top["Notas"].max() * 1.12)
    ax.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, color=COLOR_PREGRADO, label="Pregrado"),
            plt.Rectangle((0, 0), 1, 1, color=COLOR_POSGRADO, label="Posgrado"),
        ],
        loc="lower right",
    )
    _guardar(fig, "fig01_top20_cobertura.png")


def fig_brecha(brecha: pd.DataFrame) -> None:
    orden = ["Pregrado", "Posgrado"]
    datos = brecha.set_index("Grupo").loc[orden]
    fig, ejes = plt.subplots(1, 2, figsize=(11, 5))

    ejes[0].bar(orden, datos["% Cobertura institucional"], color=[COLOR_PREGRADO, COLOR_POSGRADO])
    ejes[0].set_ylabel("% del corpus")
    ejes[0].set_title("Cobertura institucional por nivel")
    for i, valor in enumerate(datos["% Cobertura institucional"]):
        ejes[0].text(i, valor + 0.4, f"{valor:.2f}%", ha="center")

    ejes[1].bar(orden, datos["% Menciones"], color=[COLOR_PREGRADO, COLOR_POSGRADO])
    ejes[1].set_ylabel("% de las menciones")
    ejes[1].set_title("Participación en las menciones")
    for i, valor in enumerate(datos["% Menciones"]):
        ejes[1].text(i, valor + 1.5, f"{valor:.2f}%", ha="center")

    for ax in ejes:
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Brecha de visibilidad Pregrado / Posgrado", fontsize=13)
    fig.tight_layout()
    _guardar(fig, "fig02_brecha_nivel.png")


def fig_evolucion(evolucion: pd.DataFrame) -> None:
    """Streamgraph de menciones por 1,000 notas (años completos)."""
    anios = evolucion[(evolucion["Periodo_Tipo"] == "Año") & (~evolucion["Es_Periodo_Parcial"])]
    pivote = anios.pivot(index="Periodo", columns="Grupo", values="Notas por 1000").sort_index()
    pivote.index = pivote.index.astype(int)
    pivot = pivote[(pivote.index >= 2003) & (pivote.index < ANIO_PARCIAL)]

    x = pivot.index.to_numpy()
    pregrado = pivot["Pregrado"].to_numpy()
    posgrado = pivot["Posgrado"].to_numpy()
    base = -(pregrado + posgrado) / 2
    techo = base + pregrado + posgrado

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.fill_between(x, base, base + pregrado, color=COLOR_PREGRADO, alpha=0.85, label="Pregrado")
    ax.fill_between(x, base + pregrado, techo, color=COLOR_POSGRADO, alpha=0.9, label="Posgrado")
    ax.plot(x, base, color="#444444", linewidth=0.8)
    ax.axhline(0, color="#999999", linewidth=0.6, linestyle=":")

    ax.set_xlabel("Año")
    ax.set_ylabel("Menciones por 1,000 notas (banda simétrica)")
    ax.set_title("Evolución de la visibilidad por nivel, 2003–2025 (streamgraph)")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _guardar(fig, "fig03_evolucion_nivel.png")


def fig_topicos_nivel(nivel: pd.DataFrame) -> None:
    pivote = nivel.pivot(index="Tema_Num", columns="Grupo", values="Peso_Medio").fillna(0)
    etiquetas = (
        nivel.drop_duplicates("Tema_Num")
        .set_index("Tema_Num")["Tema_Etiqueta"]
        .reindex(pivote.index)
        .str.split(" / ")
        .str[:2]
        .str.join(" / ")
    )
    y = np.arange(len(pivote))
    alto = 0.38
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.barh(
        y + alto / 2,
        pivote.get("Pregrado", pd.Series(0, index=pivote.index)),
        height=alto,
        color=COLOR_PREGRADO,
        label="Pregrado",
    )
    ax.barh(
        y - alto / 2,
        pivote.get("Posgrado", pd.Series(0, index=pivote.index)),
        height=alto,
        color=COLOR_POSGRADO,
        label="Posgrado",
    )
    ax.set_yticks(y, [f"T{i} · {texto}" for i, texto in zip(pivote.index, etiquetas)])
    ax.set_xlabel("Peso medio del tópico en las menciones del nivel (0–1)")
    ax.set_title("Perfil temático por nivel académico (NMF, 15 tópicos)")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    ax.invert_yaxis()
    fig.tight_layout()
    _guardar(fig, "fig04_topicos_nivel.png")


def fig_topicos_top(topicos: pd.DataFrame, cobertura: pd.DataFrame) -> None:
    top = cobertura.head(15)["Programa"].tolist()
    sub = topicos[topicos["Programa"].isin(top)]
    pivote = sub.pivot(index="Programa", columns="Tema_Num", values="Peso_Porcentaje")
    pivote = pivote.loc[top].fillna(0)

    fig, ax = plt.subplots(figsize=(13, 8))
    imagen = ax.imshow(pivote.values, aspect="auto", cmap="Blues")
    ax.set_xticks(range(len(pivote.columns)), [f"T{c}" for c in pivote.columns])
    ax.set_yticks(range(len(pivote.index)), pivote.index, fontsize=9)
    ax.set_xlabel("Tópico")
    ax.set_title("Peso de cada tópico en el Top 15 de programas (%)")
    fig.colorbar(imagen, ax=ax, label="% de la carga temática")
    fig.tight_layout()
    _guardar(fig, "fig05_topicos_top_programas.png")


def fig_categorias(definicion: pd.DataFrame) -> None:
    """Distribución global de la capa B+ (19 categorías + Otros)."""
    datos = definicion.sort_values("Notas")
    colores = [
        "#9e9e9e" if categoria == "Otros / no clasificable" else COLOR_PREGRADO
        for categoria in datos["Categoria"]
    ]
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.barh(datos["Categoria"], datos["Notas"], color=colores)
    ax.set_xlabel("Notas clasificadas en la categoría")
    ax.set_title("Categorías temáticas B+ (TF-IDF + similitud coseno, umbral 0.03)")
    for y, valor in enumerate(datos["Notas"]):
        ax.text(valor + 15, y, f"{valor:,}", va="center", fontsize=8)
    ax.set_xlim(0, datos["Notas"].max() * 1.12)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    _guardar(fig, "fig07_categorias.png")


def fig_olvido(olvido: pd.DataFrame) -> None:
    base = olvido.sort_values(["Notas", "Programa"], ascending=[False, False])
    n = len(base)
    colores = base["Categoria_Olvido"].map(
        {
            "Sin mención": COLOR_OLVIDO,
            "Mención única": COLOR_BAJA,
            "Cobertura muy baja": "#f2c6a0",
        }
    )
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.barh(base["Programa"], base["Notas"], color=colores)
    ax.set_xlabel("Notas que mencionan el programa")
    ax.set_title(f"Los {n} programas del cuartil inferior de cobertura")
    ax.grid(axis="x", alpha=0.3)
    ax.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, color=COLOR_OLVIDO, label="Sin mención"),
            plt.Rectangle((0, 0), 1, 1, color=COLOR_BAJA, label="Mención única"),
            plt.Rectangle((0, 0), 1, 1, color="#f2c6a0", label="Cobertura muy baja"),
        ],
        loc="lower right",
    )
    fig.tight_layout()
    _guardar(fig, "fig06_olvido_mediatico.png")


def main() -> None:
    cobertura = pd.read_parquet(PROCESADO / "cobertura_programas.parquet")
    brecha = pd.read_parquet(PROCESADO / "brecha_nivel.parquet")
    evolucion = pd.read_parquet(PROCESADO / "evolucion_nivel.parquet")
    olvido = pd.read_parquet(PROCESADO / "olvido_mediatico.parquet")
    topicos = pd.read_parquet(PROCESADO / "topicos_programas.parquet")
    nivel = pd.read_parquet(PROCESADO / "topicos_nivel.parquet")
    categorias = pd.read_parquet(PROCESADO / "categorias_definicion.parquet")

    fig_top20(cobertura)
    fig_brecha(brecha)
    fig_evolucion(evolucion)
    fig_topicos_nivel(nivel)
    fig_topicos_top(topicos, cobertura)
    fig_olvido(olvido)
    fig_categorias(categorias)

    print("\nFiguras de la Fase 4 generadas en reports/figures/.")


if __name__ == "__main__":
    main()
