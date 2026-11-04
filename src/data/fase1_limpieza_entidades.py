"""Fase 1 v2 - Skill 1: limpieza, extracción y estandarización de entidades.

Entrada : data/raw/noticias_raw.parquet (muestra equilibrada de la libreta
          exploratoria: máximo 10 notas por mes entre 2003 y 2026).
Salida  : data/interim/noticias_limpias.parquet (solo con --guardar).

El script implementa el Punto de Control 1: imprime el Top 20 de programas,
el desglose Pregrado/Posgrado y el Bottom 5 de programas olvidados. NO escribe
en data/interim por defecto; la persistencia requiere validación humana.

Decisiones metodológicas:
- Se usa pandas vectorizado (``str.extractall``). No hay iterrows/itertuples.
- El patrón del Skill 1 exige la taxonomía
  (Licenciatura|Ingeniería|Maestría|Doctorado|Especialidad) seguida de una
  entidad capitalizada. El conector "en" es opcional porque el archivo
  contiene formas como "Ingeniería Civil" e "Ingeniería Industrial".
- La palabra del nivel se trata sin distinguir mayúsculas: los titulares
  alternan "Maestría en X" y "maestría en X".
- Cada mención se resuelve contra el catálogo canónico de
  ``src/features/catalogo_programas.py`` (coincidencia de prefijo más larga).
  Lo que no corresponde a un programa se descarta y se reporta como ruido.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "features"))

from catalogo_programas import (
    CATALOGO,
    es_clave_exacta,
    mapear_claves,
    normalizar_claves,
    resolver_mencion,
)

# ---------------------------------------------------------------------------
# Patrón de extracción
# ---------------------------------------------------------------------------
PREFIJO = (
    r"(?P<nivel>(?i:Licenciaturas?|Ingenier[ií]as?|Maestr[ií]as?|Doctorados?"
    r"|Especialidad(?:es)?|Posgrados?))"
)
SEPARADOR = r"\s+(?:(?P<prep>en|de)\s+)?"
CONECTORES = r"(?:(?:de|del|en|y|la|las|los|el|al)\s+){0,3}"
PALABRA = r"[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñü]*"
PROGRAMA = rf"(?P<programa>{PALABRA}(?:[,\s]+{CONECTORES}{PALABRA}){{0,6}})"
PATRON = rf"\b{PREFIJO}{SEPARADOR}{PROGRAMA}"

NIVEL_SINGULAR = {
    "Licenciatura": "Licenciatura",
    "Licenciaturas": "Licenciatura",
    "Ingeniería": "Ingeniería",
    "Ingenierías": "Ingeniería",
    "Maestría": "Maestría",
    "Maestrías": "Maestría",
    "Doctorado": "Doctorado",
    "Doctorados": "Doctorado",
    "Especialidad": "Especialidad",
    "Especialidades": "Especialidad",
    "Posgrado": "Posgrado",
    "Posgrados": "Posgrado",
}


def _sin_acentos(texto: str) -> str:
    """Quita diacríticos para tolerar 'Maestria'/'Ingenieria' sin acento."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


NIVEL_SINGULAR_SIN_ACENTOS = {
    _sin_acentos(clave): valor for clave, valor in NIVEL_SINGULAR.items()
}

GRUPO = {
    "Licenciatura": "Pregrado",
    "Ingeniería": "Pregrado",
    "Maestría": "Posgrado",
    "Doctorado": "Posgrado",
    "Especialidad": "Posgrado",
    "Posgrado": "Posgrado",
}

AUTOR_DEFECTO = "Institucional / No especificado"


# ---------------------------------------------------------------------------
# Carga y limpieza
# ---------------------------------------------------------------------------
def cargar_noticias(ruta: Path) -> tuple[pd.DataFrame, int]:
    """Carga el parquet, normaliza el título y aplica las reglas de nulos."""
    df = pd.read_parquet(ruta)
    total_entrada = len(df)

    df = df.dropna(subset=["Fecha_ISO"]).copy()
    descartadas_fecha = total_entrada - len(df)

    df["Título"] = df["Título"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    if "Autor/Dependencia" in df.columns:
        df["Autor/Dependencia"] = df["Autor/Dependencia"].fillna(AUTOR_DEFECTO)
    else:
        df["Autor/Dependencia"] = AUTOR_DEFECTO

    df["Año"] = pd.to_datetime(df["Fecha_ISO"], errors="coerce").dt.year
    return df, descartadas_fecha


def _reconstruir_mencion(menciones: pd.DataFrame) -> pd.Series:
    """Reconstruye la mención completa y unifica el conector a 'en'."""
    nivel = menciones["nivel"].str.capitalize().map(_sin_acentos).map(NIVEL_SINGULAR_SIN_ACENTOS)
    if nivel.isna().any():
        faltantes = menciones.loc[nivel.isna(), "nivel"].unique()
        raise ValueError(f"Nivel no reconocido: {faltantes}")

    programa = menciones["programa"].str.replace(r"\s+", " ", regex=True).str.strip(" ,.;:")
    conector = menciones["prep"].fillna("").ne("").map({True: " en ", False: " "})
    return (nivel + conector + programa).str.replace(r"\s+", " ", regex=True).str.strip()


def _menciones_de(nivel: str, programa: str, mencion: str) -> list[str]:
    """Divide listas coordinadas ("Psicología y Comunicación") en programas.

    Solo divide cuando la mención completa no es ya un nombre oficial y todas
    las partes resuelven a programas distintos. Así no se rompen nombres como
    "Ingeniería Industrial y de Sistemas" ni "Ciencias y Tecnología de Alimentos".
    """
    if es_clave_exacta(mencion):
        return [mencion]

    partes = [
        parte.strip(" ,.;:")
        for parte in re.split(r"\s+(?:y|e)\s+|,\s+", str(programa))
        if parte.strip(" ,.;:")
    ]
    if len(partes) < 2:
        return [mencion]

    singular = NIVEL_SINGULAR_SIN_ACENTOS.get(_sin_acentos(str(nivel).capitalize()))
    if singular is None:
        return [mencion]

    candidatos = []
    for parte in partes:
        resuelto = None
        for conector in (" en ", " "):
            texto = f"{singular}{conector}{parte}"
            if resolver_mencion(texto):
                resuelto = texto
                break
        if resuelto is None:
            return [mencion]
        candidatos.append(resuelto)

    if len({resolver_mencion(candidato) for candidato in candidatos}) < 2:
        return [mencion]
    return candidatos


def extraer_menciones(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Extrae, normaliza y cataloga las menciones académicas de los títulos.

    Devuelve ``(menciones_catalogadas, ruido_descartado)``. El ruido es una
    Serie con las etiquetas que el regex capturó pero que no son programas
    del catálogo (honoris causa, divisiones, campus, etc.).
    """
    crudas = df["Título"].str.extractall(PATRON)
    crudas = crudas.reset_index(level=1, drop=True).join(
        df[["Fecha_ISO", "Año", "Título", "Autor/Dependencia", "Enlace"]],
        how="left",
    )

    crudas["Mencion"] = _reconstruir_mencion(crudas)
    crudas["_candidatos"] = [
        _menciones_de(nivel, programa, mencion)
        for nivel, programa, mencion in zip(
            crudas["nivel"], crudas["programa"], crudas["Mencion"], strict=True
        )
    ]
    crudas = crudas.explode("_candidatos", ignore_index=True)
    crudas["Mencion"] = crudas["_candidatos"]
    crudas["clave"] = normalizar_claves(crudas["Mencion"])
    crudas["Programa"] = mapear_claves(crudas["clave"])

    ruido = crudas.loc[crudas["Programa"].isna(), "Mencion"].value_counts()
    menciones = crudas.dropna(subset=["Programa"]).copy()

    menciones["Nivel"] = menciones["Programa"].str.extract(
        r"^(Licenciatura|Ingeniería|Maestría|Doctorado|Especialidad|Posgrado)",
        expand=False,
    )
    menciones["Grupo"] = menciones["Nivel"].map(GRUPO)
    if menciones["Grupo"].isna().any():
        faltantes = menciones.loc[menciones["Grupo"].isna(), "Programa"].unique()
        raise ValueError(f"Programa sin grupo Pregrado/Posgrado: {faltantes}")

    # Una nota puede mencionar el mismo programa más de una vez; se cuenta una.
    menciones = menciones.drop_duplicates(subset=["Enlace", "Programa"])
    menciones = menciones[
        [
            "Fecha_ISO",
            "Año",
            "Título",
            "Autor/Dependencia",
            "Enlace",
            "Mencion",
            "Nivel",
            "Grupo",
            "Programa",
        ]
    ].sort_values(["Año", "Fecha_ISO", "Programa"])
    return menciones, ruido


# ---------------------------------------------------------------------------
# Frecuencias y tablas del Punto de Control 1
# ---------------------------------------------------------------------------
def calcular_frecuencias(menciones: pd.DataFrame, total_notas: int) -> pd.DataFrame:
    notas_con_programa = menciones["Enlace"].nunique()
    freq = (
        menciones.groupby(["Programa", "Nivel", "Grupo"], as_index=False)
        .agg(Notas=("Enlace", "nunique"))
        .sort_values(["Notas", "Programa"], ascending=[False, True])
        .reset_index(drop=True)
    )
    freq["% del total"] = (freq["Notas"] / total_notas * 100).round(2)
    freq["% del subconjunto"] = (freq["Notas"] / notas_con_programa * 100).round(1)
    return freq


def cobertura_del_catalogo(freq: pd.DataFrame) -> pd.DataFrame:
    """Cruce del catálogo completo con las frecuencias observadas.

    Incluye los programas canónicos con cero menciones: son la evidencia de
    los "olvidados" que no aparecen ni una vez en la muestra.
    """
    catalogo = pd.DataFrame({"Programa": CATALOGO}).drop_duplicates()
    catalogo["Nivel"] = catalogo["Programa"].str.extract(
        r"^(Licenciatura|Ingeniería|Maestría|Doctorado|Especialidad|Posgrado)",
        expand=False,
    )
    catalogo["Grupo"] = catalogo["Nivel"].map(GRUPO)

    cobertura = catalogo.merge(freq[["Programa", "Notas"]], on="Programa", how="left")
    cobertura["Notas"] = cobertura["Notas"].fillna(0).astype(int)
    return cobertura.sort_values(
        ["Notas", "Grupo", "Programa"], ascending=[True, True, True]
    ).reset_index(drop=True)


def _tabla_top(freq: pd.DataFrame, n: int) -> pd.DataFrame:
    tabla = freq.head(n).copy()
    tabla.insert(0, "#", range(1, len(tabla) + 1))
    return tabla[["#", "Programa", "Nivel", "Grupo", "Notas", "% del total", "% del subconjunto"]]


def _tabla_bottom(cobertura: pd.DataFrame, n: int) -> pd.DataFrame:
    return cobertura.head(n)[["Programa", "Nivel", "Grupo", "Notas"]]


def _muestra_estratificada(
    df: pd.DataFrame, n_pregrado: int = 3, n_posgrado: int = 2
) -> pd.DataFrame:
    """Toma casos del fondo alternando Pregrado y Posgrado.

    Cuando decenas de programas empatan en el mismo número de notas, un
    ``head(5)`` concentraría el listado en el primer grupo alfabético. Se
    intenta 3 casos de Pregrado y 2 de Posgrado; si un grupo no tiene
    suficientes, se completa con el otro para no devolver menos de 5 filas.
    """
    total = n_pregrado + n_posgrado
    pregrado = df[df["Grupo"] == "Pregrado"].head(n_pregrado)
    posgrado = df[df["Grupo"] == "Posgrado"].head(n_posgrado)
    seleccion = pd.concat([pregrado, posgrado])

    if len(seleccion) < total:
        resto = df.drop(seleccion.index).head(total - len(seleccion))
        seleccion = pd.concat([seleccion, resto])

    return seleccion[["Programa", "Nivel", "Grupo", "Notas"]]


def _muestra_fondo(
    cobertura: pd.DataFrame, n_pregrado: int = 3, n_posgrado: int = 2
) -> pd.DataFrame:
    """Muestra representativa de los programas con cero menciones."""
    return _muestra_estratificada(cobertura[cobertura["Notas"] == 0], n_pregrado, n_posgrado)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fase 1 v2 - Extracción y estandarización de entidades académicas"
    )
    parser.add_argument(
        "--input",
        default="data/raw/noticias_raw.parquet",
        help="Parquet de entrada (por defecto, la muestra de la libreta).",
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--bottom", type=int, default=5)
    parser.add_argument(
        "--guardar",
        action="store_true",
        help="Persistir en data/interim (requiere validación del Punto de Control 1).",
    )
    parser.add_argument(
        "--ruido",
        type=int,
        default=10,
        help="Número de etiquetas de ruido a mostrar en el diagnóstico.",
    )
    args = parser.parse_args()

    ruta = RAIZ / args.input
    df, descartadas_fecha = cargar_noticias(ruta)
    menciones, ruido = extraer_menciones(df)
    freq = calcular_frecuencias(menciones, total_notas=len(df))
    cobertura = cobertura_del_catalogo(freq)

    notas_con_programa = menciones["Enlace"].nunique()
    sin_mencion = cobertura[cobertura["Notas"] == 0]
    activos = cobertura[cobertura["Notas"] > 0].sort_values(
        ["Notas", "Programa"], ascending=[True, True]
    )

    print("=" * 78)
    print("PUNTO DE CONTROL 1 - FASE 1: ENTIDADES ACADÉMICAS")
    print("=" * 78)
    print(f"Fuente                         : {args.input}")
    print(f"Notas de entrada               : {len(df) + descartadas_fecha:,}")
    print(f"Descartadas por Fecha_ISO nula : {descartadas_fecha:,}")
    print(f"Notas analizadas               : {len(df):,}")
    print(
        f"Notas con al menos un programa : {notas_con_programa:,} "
        f"({notas_con_programa / len(df) * 100:.2f}%)"
    )
    print(f"Menciones catalogadas          : {len(menciones):,}")
    print(f"Programas únicos observados    : {freq.shape[0]:,} de {len(cobertura):,} del catálogo")
    print(f"Menciones descartadas (ruido)  : {int(ruido.sum()):,} ({ruido.size:,} etiquetas)")
    print(f"Autor/Dependencia              : 100% con '{AUTOR_DEFECTO}'")

    print("\n" + "-" * 78)
    print("DESGLOSE POR NIVEL")
    print("-" * 78)
    por_grupo = (
        menciones.groupby("Grupo")
        .agg(Programas=("Programa", "nunique"), Menciones=("Programa", "size"))
        .reset_index()
    )
    por_grupo["% de menciones"] = (por_grupo["Menciones"] / len(menciones) * 100).round(1)
    print(por_grupo.to_markdown(index=False))

    print("\n" + "-" * 78)
    print(f"TOP {args.top} DE PROGRAMAS CON MAYOR COBERTURA")
    print("-" * 78)
    print(_tabla_top(freq, args.top).to_markdown(index=False))

    print("\n" + "-" * 78)
    print("TOP 10 PREGRADO")
    print("-" * 78)
    print(_tabla_top(freq[freq["Grupo"] == "Pregrado"], 10).to_markdown(index=False))

    print("\n" + "-" * 78)
    print("TOP 10 POSGRADO")
    print("-" * 78)
    print(_tabla_top(freq[freq["Grupo"] == "Posgrado"], 10).to_markdown(index=False))

    print("\n" + "-" * 78)
    print("DISTRIBUCIÓN DE COBERTURA")
    print("-" * 78)
    print(f"  Programas con 3 o más notas : {int((freq['Notas'] >= 3).sum()):,}")
    print(f"  Programas con 2 notas       : {int((freq['Notas'] == 2).sum()):,}")
    print(f"  Programas con 1 nota        : {int((freq['Notas'] == 1).sum()):,}")
    print(f"  Programas sin menciones     : {len(sin_mencion):,}")
    nota_corte = int(freq.head(args.top)["Notas"].min())
    if len(freq) > args.top:
        nota_siguiente = int(freq.iloc[args.top]["Notas"])
        if nota_siguiente == nota_corte:
            print(
                f"  Empate en la frontera del Top {args.top}: "
                f"{int((freq['Notas'] == nota_corte).sum())} programas "
                f"tienen {nota_corte} notas."
            )
        else:
            print(
                f"  Corte del Top {args.top}: {nota_corte} notas; "
                f"el siguiente programa tiene {nota_siguiente}."
            )

    print("\n" + "-" * 78)
    print(f"BOTTOM {args.bottom} DE PROGRAMAS OLVIDADOS (CATÁLOGO COMPLETO)")
    print("-" * 78)
    print(
        f"Programas del catálogo sin ninguna mención: {len(sin_mencion):,} de {len(cobertura):,}"
    )
    print(sin_mencion.groupby("Grupo").size().to_string())
    n_posgrado = args.bottom // 2
    n_pregrado = args.bottom - n_posgrado
    muestra_fondo = _muestra_fondo(cobertura, n_pregrado, n_posgrado)
    conteo_fondo = muestra_fondo["Grupo"].value_counts().to_dict()
    print(
        "\nLos programas sin menciones comparten el último lugar; no hay un "
        "orden único entre ellos.\n"
        f"Se muestran {len(muestra_fondo)} casos representativos: "
        f"{conteo_fondo.get('Pregrado', 0)} Pregrado y "
        f"{conteo_fondo.get('Posgrado', 0)} Posgrado, en orden alfabético.\n"
    )
    print(muestra_fondo.to_markdown(index=False))

    print("\n" + "-" * 78)
    print(f"BOTTOM {args.bottom} ENTRE PROGRAMAS CON AL MENOS UNA MENCIÓN")
    print("-" * 78)
    muestra_activos = _muestra_estratificada(activos, n_pregrado, n_posgrado)
    conteo_activos = muestra_activos["Grupo"].value_counts().to_dict()
    print(
        f"Programas con exactamente una mención: "
        f"{int((freq['Notas'] == 1).sum()):,}. "
        f"Se muestran {len(muestra_activos)} casos representativos: "
        f"{conteo_activos.get('Pregrado', 0)} Pregrado y "
        f"{conteo_activos.get('Posgrado', 0)} Posgrado.\n"
    )
    print(muestra_activos.to_markdown(index=False))

    if args.ruido:
        print("\n" + "-" * 78)
        print(f"DIAGNÓSTICO DE RUIDO DESCARTADO (TOP {args.ruido})")
        print("-" * 78)
        print(ruido.head(args.ruido).to_frame("Menciones").to_markdown())

    if args.guardar:
        salida = RAIZ / "data/interim/noticias_limpias.parquet"
        salida.parent.mkdir(parents=True, exist_ok=True)
        menciones.to_parquet(salida, index=False)
        print(f"\nGuardado en {salida.relative_to(RAIZ)}")
    else:
        print(
            "\n[Punto de Control 1] No se escribió nada en data/interim. "
            "La persistencia requiere validación explícita."
        )


if __name__ == "__main__":
    main()
