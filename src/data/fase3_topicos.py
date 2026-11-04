"""Fase 3 - Skill 2: modelado de tópicos sobre el cuerpo de las noticias.

Entrada
    data/interim/noticias_limpias_full.parquet (menciones título + cuerpo)
    data/interim/cuerpos_full.parquet         (texto completo por nota)

Salida
    data/processed/topicos_programas.parquet (largo: Programa x Tema)
    data/processed/topicos_definicion.parquet (palabras por tema)
    data/processed/topicos_nivel.parquet      (peso medio por grupo)
    data/processed/resumen_pc2.parquet       (actualizado con el tópico principal)

Decisiones metodológicas
- Técnica: NMF (Non-negative Matrix Factorization) de scikit-learn sobre una
  representación TF-IDF (TF sublineal, stop words en español). Se probó LDA
  primero, pero con prosa institucional tan homogénea colapsó casi todos los
  documentos en un tópico "académico/investigación" (19,321 de 20,683). NMF
  produce tópicos disjuntos e interpretables y es igual de ligero: sin GPU,
  sin embeddings y con semilla fija para reproducibilidad.
- Unidad documental: una mención (Enlace, Programa); el texto es el cuerpo de
  la nota que contiene la mención. Así el tópico describe el contexto en que
  aparece cada programa, no el programa en abstracto.
- Un único modelo global (15 tópicos) permite comparar Pregrado y Posgrado en
  el mismo espacio temático.
- El tópico principal de un programa es el de mayor carga acumulada en sus
  menciones; se persisten el top-3 y su participación relativa (%) para
  dimensionar la evidencia.
- La coherencia se mide con NPMI sobre la matriz binaria documento-término.
  Se reporta por tópico y en promedio, junto con la diversidad de términos.
- Las etiquetas de los tópicos se asignan a mano a partir de las palabras de
  mayor peso, para que la lectura no dependa de la primera palabra suelta.
- Se excluyen del vocabulario los términos institucionales, taxonómicos y las
  muletillas periodísticas ("unison", "investigación", "dijo", ...) para que
  los tópicos reflejen temas y no la jerga administrativa.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "features"))

SEED = 20261103
N_PALABRAS_ETIQUETA = 6
N_PALABRAS_COHERENCIA = 10
TOP_N = 3

# Nombres legibles asignados a mano tras revisar las palabras de cada tópico.
# La clave es la palabra de mayor peso; si no hay entrada, se usa la etiqueta
# automática (tres primeras palabras).
ETIQUETAS_MANUALES: dict[str, str] = {
    "ser": "Sociedad y vida universitaria",
    "premio": "Premios y trayectorias",
    "artes": "Artes, música y danza",
    "salud": "Salud y enfermería",
    "aspirantes": "Admisión e ingreso",
    "rector": "Gobierno universitario",
    "alimentos": "Alimentos y nutrición",
    "acreditación": "Calidad y evaluación educativa",
    "evento": "Eventos académicos",
    "ceremonia": "Egreso y graduación",
    "feria": "Divulgación científica",
    "semestre": "Vida estudiantil y movilidad",
    "industrial": "Ingeniería y tecnología",
    "derecho": "Derecho y ciencias sociales",
    "unidad": "Unidades regionales",
}

# Stop words en español (la versión instalada de scikit-learn solo trae
# "english"; se declara la lista explícita para no depender de NLTK).
STOP_WORDS_ES = [
    "a",
    "al",
    "algo",
    "algunas",
    "algunos",
    "ante",
    "antes",
    "como",
    "con",
    "contra",
    "cual",
    "cuando",
    "de",
    "del",
    "desde",
    "donde",
    "durante",
    "e",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "erais",
    "eran",
    "eras",
    "eres",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estaba",
    "estabais",
    "estaban",
    "estabas",
    "estad",
    "estada",
    "estadas",
    "estado",
    "estados",
    "estamos",
    "estando",
    "estar",
    "estaremos",
    "estará",
    "estarán",
    "estarás",
    "estaré",
    "estaréis",
    "estaría",
    "estaríais",
    "estaríamos",
    "estarían",
    "estarías",
    "estas",
    "este",
    "estemos",
    "esto",
    "estos",
    "estoy",
    "estuve",
    "estuviera",
    "estuvierais",
    "estuvieran",
    "estuvieras",
    "estuvieron",
    "estuviese",
    "estuvieseis",
    "estuviesen",
    "estuvieses",
    "estuvimos",
    "estuviste",
    "estuvisteis",
    "estuviéramos",
    "estuviésemos",
    "estuvo",
    "está",
    "estábamos",
    "estáis",
    "están",
    "estás",
    "esté",
    "estéis",
    "estén",
    "estés",
    "fue",
    "fuera",
    "fuerais",
    "fueran",
    "fueras",
    "fueron",
    "fuese",
    "fueseis",
    "fuesen",
    "fueses",
    "fui",
    "fuimos",
    "fuiste",
    "fuisteis",
    "fuéramos",
    "fuésemos",
    "ha",
    "habida",
    "habidas",
    "habido",
    "habidos",
    "habiendo",
    "habremos",
    "habrá",
    "habrán",
    "habrás",
    "habré",
    "habréis",
    "habría",
    "habríais",
    "habríamos",
    "habrían",
    "habrías",
    "habéis",
    "había",
    "habíais",
    "habíamos",
    "habían",
    "habías",
    "han",
    "has",
    "hasta",
    "hay",
    "haya",
    "hayamos",
    "hayan",
    "hayas",
    "hayáis",
    "he",
    "hemos",
    "hube",
    "hubiera",
    "hubierais",
    "hubieran",
    "hubieras",
    "hubieron",
    "hubiese",
    "hubieseis",
    "hubiesen",
    "hubieses",
    "hubimos",
    "hubiste",
    "hubisteis",
    "hubiéramos",
    "hubiésemos",
    "hubo",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "mucho",
    "muchos",
    "muy",
    "más",
    "mé",
    "mí",
    "mía",
    "mías",
    "mío",
    "míos",
    "nada",
    "ni",
    "no",
    "nos",
    "nosotras",
    "nosotros",
    "nuestra",
    "nuestras",
    "nuestro",
    "nuestros",
    "o",
    "os",
    "otra",
    "otras",
    "otro",
    "otros",
    "para",
    "pero",
    "poco",
    "por",
    "porque",
    "que",
    "quien",
    "quienes",
    "qué",
    "se",
    "sea",
    "seamos",
    "sean",
    "seas",
    "seremos",
    "será",
    "serán",
    "serás",
    "seré",
    "seréis",
    "sería",
    "seríais",
    "seríamos",
    "serían",
    "serías",
    "seáis",
    "sido",
    "siendo",
    "sin",
    "sobre",
    "sois",
    "somos",
    "son",
    "soy",
    "su",
    "sus",
    "suya",
    "suyas",
    "suyo",
    "suyos",
    "sí",
    "también",
    "tanto",
    "te",
    "tendremos",
    "tendrá",
    "tendrán",
    "tendrás",
    "tendré",
    "tendréis",
    "tendría",
    "tendríais",
    "tendríamos",
    "tendrían",
    "tendrías",
    "tened",
    "tenemos",
    "tenga",
    "tengamos",
    "tengan",
    "tengas",
    "tengo",
    "tengáis",
    "tenida",
    "tenidas",
    "tenido",
    "tenidos",
    "teniendo",
    "tenéis",
    "tenía",
    "teníais",
    "teníamos",
    "tenían",
    "tenías",
    "ti",
    "tiene",
    "tienen",
    "tienes",
    "todo",
    "todos",
    "tu",
    "tus",
    "tuve",
    "tuviera",
    "tuvierais",
    "tuvieran",
    "tuvieras",
    "tuvieron",
    "tuviese",
    "tuvieseis",
    "tuviesen",
    "tuvieses",
    "tuvimos",
    "tuviste",
    "tuvisteis",
    "tuviéramos",
    "tuviésemos",
    "tuvo",
    "tuya",
    "tuyas",
    "tuyo",
    "tuyos",
    "tú",
    "un",
    "una",
    "unas",
    "uno",
    "unos",
    "vosotras",
    "vosotros",
    "vuestra",
    "vuestras",
    "vuestro",
    "vuestros",
    "y",
    "ya",
    "yo",
    # Jerga institucional y taxonómica: no aporta a la temática.
    "unison",
    "universidad",
    "licenciatura",
    "licenciaturas",
    "ingeniería",
    "ingenierías",
    "maestría",
    "maestrías",
    "doctorado",
    "doctorados",
    "especialidad",
    "especialidades",
    "posgrado",
    "posgrados",
    "carrera",
    "carreras",
    "programa",
    "programas",
    "facultad",
    "facultades",
    "departamento",
    "departamentos",
    "división",
    "divisiones",
    "alumnos",
    "alumnas",
    "alumno",
    "alumna",
    "estudiantes",
    "estudiante",
    "docentes",
    "profesores",
    "investigadores",
    "unison",
    # Verbos de declaración y muletillas del género periodístico.
    "dijo",
    "señaló",
    "indicó",
    "agregó",
    "explicó",
    "mencionó",
    "realizó",
    "realizar",
    "expresó",
    "comentó",
    "detalló",
    "informó",
    "parte",
    "trabajo",
    "estudios",
    "ciencias",
    "nacional",
    "méxico",
    "mexico",
    # Adjetivos y verbos institucionales ubicuos que no discriminan temas.
    "académico",
    "académica",
    "académicos",
    "académicas",
    "investigación",
    "investigaciones",
    "desarrollo",
    "institución",
    "institucional",
    "así",
    "lugar",
    "campus",
    "servicios",
    "información",
    "problema",
    "emite",
    "llevará",
    "permanecerán",
    "acerque",
    "descubran",
    "imposición",
    "usted",
    "ustedes",
    "dra",
    "dr",
    "00",
    "mx",
    "www",
    "uson",
    "realiza",
    "realizan",
    "realizado",
    "mediante",
    "través",
    "además",
    "aunque",
    "mientras",
    "respecto",
    "nuevo",
    "nueva",
    "nuevos",
    "nuevas",
]


# ---------------------------------------------------------------------------
# Carga y documentos
# ---------------------------------------------------------------------------
def cargar_menciones(ruta: Path) -> pd.DataFrame:
    """Menciones de la Fase 1 full-text con tipos consistentes."""
    menciones = pd.read_parquet(ruta)
    menciones["Año"] = pd.to_numeric(menciones["Año"], errors="coerce").astype("Int64")
    return menciones.dropna(subset=["Año"]).copy()


def cargar_cuerpos(ruta: Path) -> pd.DataFrame:
    """Cuerpos válidos, sin duplicados por enlace."""
    cuerpos = pd.read_parquet(ruta, columns=["Enlace", "cuerpo"])
    cuerpos = cuerpos[cuerpos["cuerpo"].fillna("").str.len().gt(0)]
    return cuerpos.drop_duplicates(subset=["Enlace"], keep="last")


def construir_documentos(menciones: pd.DataFrame, cuerpos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por mención (Enlace, Programa) con el cuerpo de su nota."""
    docs = menciones.merge(cuerpos, on="Enlace", how="inner")
    docs["Texto"] = docs["cuerpo"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    docs["Texto"] = docs["Texto"].str.slice(0, 1500)
    docs = docs[docs["Texto"].str.len().gt(0)]
    docs = docs.drop_duplicates(subset=["Enlace", "Programa"])
    return docs[["Enlace", "Año", "Programa", "Nivel", "Grupo", "Fuente_Mencion", "Texto"]]


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
def vectorizar(textos: pd.Series) -> tuple[TfidfVectorizer, object]:
    """TF-IDF con stop words en español y vocabulario acotado."""
    vectorizador = TfidfVectorizer(
        stop_words=STOP_WORDS_ES,
        token_pattern=r"(?u)\b[\wáéíóúñü]+\b",
        lowercase=True,
        sublinear_tf=True,
        min_df=10,
        max_df=0.5,
        max_features=20000,
        ngram_range=(1, 1),
    )
    return vectorizador, vectorizador.fit_transform(textos)


def entrenar_nmf(matriz, n_topicos: int) -> NMF:
    """Ajusta NMF con semilla fija para reproducibilidad."""
    modelo = NMF(
        n_components=n_topicos,
        random_state=SEED,
        init="nndsvda",
        max_iter=300,
    )
    modelo.fit(matriz)
    return modelo


def etiquetas_topicos(
    modelo: NMF,
    vectorizador: TfidfVectorizer,
    n_palabras: int = N_PALABRAS_ETIQUETA,
) -> tuple[list[str], list[list[str]]]:
    """Etiqueta legible y palabras principales por tópico."""
    vocabulario = np.asarray(vectorizador.get_feature_names_out())
    etiquetas, palabras = [], []
    for topico in modelo.components_:
        indices = np.argsort(topico)[::-1][:n_palabras]
        terminos = vocabulario[indices].tolist()
        palabras.append(terminos)
        automatica = f"{terminos[0]} / {terminos[1]} / {terminos[2]}"
        etiquetas.append(ETIQUETAS_MANUALES.get(terminos[0], automatica))
    return etiquetas, palabras


def coherencia_npmi(
    modelo: NMF,
    vectorizador: TfidfVectorizer,
    matriz,
    n_palabras: int = N_PALABRAS_COHERENCIA,
) -> tuple[list[float], float]:
    """Coherencia NPMI y diversidad de los tópicos.

    NPMI mide si las palabras de un tópico coaparecen en las notas más de lo
    esperado por azar. Se calcula sobre la matriz binaria documento-término,
    sin dependencias adicionales.
    """
    vocabulario = np.asarray(vectorizador.get_feature_names_out())
    binaria = (matriz > 0).astype(np.float32)
    n_docs = binaria.shape[0]
    frecuencia = np.asarray(binaria.sum(axis=0)).ravel()

    indices_por_topico = [
        np.argsort(topico)[::-1][:n_palabras] for topico in modelo.components_
    ]
    usados = sorted({int(i) for indices in indices_por_topico for i in indices})
    posicion = {global_: local for local, global_ in enumerate(usados)}

    submatriz = binaria[:, usados]
    coocurrencia = (submatriz.T @ submatriz).toarray()
    frec_sub = frecuencia[usados]

    coherencias = []
    for indices in indices_por_topico:
        pares = []
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                a, b = posicion[int(indices[i])], posicion[int(indices[j])]
                p_ab = coocurrencia[a, b] / n_docs
                if p_ab <= 0:
                    continue
                p_a = frec_sub[a] / n_docs
                p_b = frec_sub[b] / n_docs
                npmi = np.log(p_ab / (p_a * p_b)) / -np.log(p_ab)
                pares.append(npmi)
        coherencias.append(float(np.mean(pares)) if pares else 0.0)

    terminos = {
        vocabulario[int(i)] for indices in indices_por_topico for i in indices
    }
    diversidad = len(terminos) / (len(indices_por_topico) * n_palabras)
    return coherencias, diversidad


def topicos_por_programa(docs: pd.DataFrame, modelo: NMF, matriz, n_topicos: int) -> pd.DataFrame:
    """Distribución temática agregada por programa (formato largo)."""
    columnas = [f"Tema_{k + 1}" for k in range(n_topicos)]
    pesos = pd.DataFrame(modelo.transform(matriz), columns=columnas)
    pesos["Programa"] = docs["Programa"].to_numpy()
    pesos["Nivel"] = docs["Nivel"].to_numpy()
    pesos["Grupo"] = docs["Grupo"].to_numpy()

    sumas = pesos.groupby(["Programa", "Nivel", "Grupo"], as_index=False)[columnas].sum()
    total = sumas.set_index("Programa")[columnas].sum(axis=1)
    largo = sumas.melt(
        id_vars=["Programa", "Nivel", "Grupo"],
        value_vars=columnas,
        var_name="Tema",
        value_name="Peso",
    )
    largo["Tema_Num"] = largo["Tema"].str.removeprefix("Tema_").astype(int)
    largo["Peso_Porcentaje"] = (largo["Peso"] / largo["Programa"].map(total) * 100).round(2)
    largo["Ranking"] = (
        largo.groupby("Programa")["Peso"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    largo["Es_Top3"] = largo["Ranking"] <= TOP_N

    return largo


def frecuencia_programas(docs: pd.DataFrame) -> pd.DataFrame:
    """Notas y menciones por programa (para unir al resultado)."""
    return docs.groupby(["Programa", "Nivel", "Grupo"], as_index=False).agg(
        Notas=("Enlace", "nunique"), Menciones=("Enlace", "size")
    )


def top_topicos(largo: pd.DataFrame, n: int = TOP_N) -> pd.DataFrame:
    """Formato ancho con los n tópicos de mayor peso por programa."""
    top = largo[largo["Ranking"] <= n].copy()
    top["Posicion"] = (
        top.groupby("Programa")["Ranking"].rank(method="first").astype(int)
    )
    ancho = top.pivot(
        index="Programa",
        columns="Posicion",
        values=["Tema_Etiqueta", "Peso_Porcentaje"],
    )
    ancho.columns = [f"{columna}_{posicion}" for columna, posicion in ancho.columns]
    return ancho.reset_index()


# ---------------------------------------------------------------------------
# Punto de Control 3
# ---------------------------------------------------------------------------
def imprimir_pc3(
    docs: pd.DataFrame,
    largo: pd.DataFrame,
    etiquetas: list[str],
    palabras: list[list[str]],
    programa_principal: pd.DataFrame,
    por_grupo: pd.DataFrame,
    n_topicos: int,
    top: int,
    coherencias: list[float],
    diversidad: float,
) -> None:
    print("=" * 82)
    print("PUNTO DE CONTROL 3 - FASE 3: MODELADO DE TÓPICOS")
    print("=" * 82)
    print("Modelo                : NMF (scikit-learn) sobre TF-IDF")
    print("Unidad documental     : una mención (Enlace, Programa) -> cuerpo de la nota")
    print(f"Documentos            : {len(docs):,}")
    print(f"Programas con texto   : {docs['Programa'].nunique():,}")
    print(f"Tópicos               : {n_topicos}")
    print(f"Semilla               : {SEED}")

    print("\n" + "-" * 82)
    print("TÓPICOS Y PALABRAS PRINCIPALES")
    print("-" * 82)
    tabla = pd.DataFrame(
        {
            "Tema": range(1, n_topicos + 1),
            "Etiqueta": etiquetas,
            "Palabras clave": [" / ".join(p) for p in palabras],
            "Coherencia NPMI": np.round(coherencias, 3),
        }
    )
    print(tabla.to_markdown(index=False))
    print(
        f"\nCoherencia NPMI media: {np.mean(coherencias):.3f} | "
        f"Diversidad de términos: {diversidad:.2f}"
    )

    print("\n" + "-" * 82)
    print("DISTRIBUCIÓN DE PROGRAMAS POR TÓPICO PRINCIPAL")
    print("-" * 82)
    conteo = programa_principal.groupby("Tema_Num").size().rename("Programas")
    conteo.index = [f"Tema {i} - {etiquetas[i - 1]}" for i in conteo.index]
    print(conteo.to_markdown())

    print("\n" + "-" * 82)
    print(f"TOP {top} DE PROGRAMAS Y SU TÓPICO PRINCIPAL")
    print("-" * 82)
    columnas = [
        "Programa",
        "Grupo",
        "Notas",
        "Tema_Num",
        "Tema_Etiqueta",
        "Peso_Porcentaje",
    ]
    print(programa_principal.head(top)[columnas].to_markdown(index=False))

    print("\n" + "-" * 82)
    print("DISTRIBUCIÓN TEMÁTICA POR NIVEL (peso medio)")
    print("-" * 82)
    print(por_grupo.round(2).to_markdown())

    print("\n" + "-" * 82)
    print("ARCHIVOS GENERADOS")
    print("-" * 82)
    print("  data/processed/topicos_programas.parquet")
    print("  data/processed/topicos_definicion.parquet")
    print("  data/processed/topicos_nivel.parquet")
    print("  data/processed/resumen_pc2.parquet (columna Tópico Principal Asociado)")

    print(
        "\n[Punto de Control 3] Tópicos asignados. La Fase 4 (narrativa en tres actos) "
        "requiere validación explícita."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 3 - Modelado de tópicos por programa")
    parser.add_argument("--input", default="data/interim/noticias_limpias_full.parquet")
    parser.add_argument("--cuerpos", default="data/interim/cuerpos_full.parquet")
    parser.add_argument("--salida", default="data/processed/topicos_programas.parquet")
    parser.add_argument("--n_topicos", type=int, default=15)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    menciones = cargar_menciones(RAIZ / args.input)
    cuerpos = cargar_cuerpos(RAIZ / args.cuerpos)
    docs = construir_documentos(menciones, cuerpos)

    print(
        f"Menciones cargadas: {len(menciones):,} | cuerpos: {len(cuerpos):,} | "
        f"documentos para el modelo: {len(docs):,}"
    )

    vectorizador, matriz = vectorizar(docs["Texto"])
    print(f"Matriz TF-IDF: {matriz.shape[0]:,} documentos x {matriz.shape[1]:,} términos")

    modelo = entrenar_nmf(matriz, args.n_topicos)
    etiquetas, palabras = etiquetas_topicos(modelo, vectorizador)
    coherencias, diversidad = coherencia_npmi(modelo, vectorizador, matriz)

    largo = topicos_por_programa(docs, modelo, matriz, args.n_topicos)
    frecuencias = frecuencia_programas(docs)

    etiqueta_por_tema = {k + 1: etiquetas[k] for k in range(args.n_topicos)}
    largo["Tema_Etiqueta"] = largo["Tema_Num"].map(etiqueta_por_tema)

    principal = largo.loc[largo.groupby("Programa")["Peso"].idxmax()].copy()
    principal = principal.merge(frecuencias, on=["Programa", "Nivel", "Grupo"], how="left")
    principal = principal.sort_values(["Notas", "Programa"], ascending=[False, True]).reset_index(
        drop=True
    )

    largo = largo.merge(frecuencias, on=["Programa", "Nivel", "Grupo"], how="left")
    largo = largo.sort_values(
        ["Programa", "Peso_Porcentaje"], ascending=[True, False]
    ).reset_index(drop=True)

    salida = RAIZ / args.salida
    salida.parent.mkdir(parents=True, exist_ok=True)
    largo.to_parquet(salida, index=False, compression="zstd")

    # Actualización del resumen del Punto de Control 2.
    resumen_path = RAIZ / "data/processed/resumen_pc2.parquet"
    resumen = pd.read_parquet(resumen_path)
    ancho = top_topicos(largo)
    columnas = {
        "Tema_Etiqueta_1": "Tópico Principal Asociado",
        "Peso_Porcentaje_1": "Peso Tópico Principal (%)",
        "Tema_Etiqueta_2": "Tópico 2 Asociado",
        "Peso_Porcentaje_2": "Peso Tópico 2 (%)",
        "Tema_Etiqueta_3": "Tópico 3 Asociado",
        "Peso_Porcentaje_3": "Peso Tópico 3 (%)",
    }
    for origen, destino in columnas.items():
        if origen in ancho.columns:
            resumen[destino] = resumen["Programa"].map(ancho.set_index("Programa")[origen])
    resumen["Tópico Principal Asociado"] = resumen["Tópico Principal Asociado"].fillna(
        "Sin menciones (Fase 3)"
    )
    resumen.to_parquet(resumen_path, index=False, compression="zstd")

    # Distribución media de temas por nivel (cada documento normalizado a 100%).
    columnas_tema = [f"Tema_{k + 1}" for k in range(args.n_topicos)]
    pesos_doc = pd.DataFrame(modelo.transform(matriz), columns=columnas_tema)
    total_doc = pesos_doc.sum(axis=1).replace(0, np.nan)
    pesos_doc = pesos_doc.div(total_doc, axis=0).fillna(0)
    pesos_doc["Grupo"] = docs["Grupo"].to_numpy()
    por_grupo = pesos_doc.groupby("Grupo")[columnas_tema].mean()
    por_grupo.columns = [f"Tema {k + 1}" for k in range(args.n_topicos)]

    nivel = por_grupo.reset_index().melt(id_vars="Grupo", var_name="Tema", value_name="Peso_Medio")
    nivel["Tema_Num"] = nivel["Tema"].str.removeprefix("Tema ").astype(int)
    nivel["Tema_Etiqueta"] = nivel["Tema_Num"].map(etiqueta_por_tema)
    nivel.to_parquet(
        RAIZ / "data/processed/topicos_nivel.parquet", index=False, compression="zstd"
    )

    definicion = pd.DataFrame(
        {
            "Tema": range(1, args.n_topicos + 1),
            "Etiqueta": etiquetas,
            "Palabras": [" / ".join(p) for p in palabras],
            "Coherencia_NPMI": np.round(coherencias, 4),
        }
    )
    definicion.to_parquet(RAIZ / "data/processed/topicos_definicion.parquet", index=False)

    imprimir_pc3(
        docs,
        largo,
        etiquetas,
        palabras,
        principal,
        por_grupo,
        args.n_topicos,
        args.top,
        coherencias,
        diversidad,
    )


if __name__ == "__main__":
    main()
