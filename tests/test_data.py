"""Pruebas de la Fase 1 v2 (Skill 1): extracción, clasificación y normalización."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "data"))
sys.path.insert(0, str(RAIZ / "src" / "features"))

from catalogo_programas import es_clave_exacta, resolver_mencion
from fase1_limpieza_entidades import (
    AUTOR_DEFECTO,
    CATALOGO,
    _menciones_de,
    calcular_frecuencias,
    cargar_noticias,
    cobertura_del_catalogo,
    extraer_menciones,
)


def _noticias(titulos: list[str], enlaces: list[str] | None = None) -> pd.DataFrame:
    n = len(titulos)
    return pd.DataFrame(
        {
            "Título": titulos,
            "Fecha_ISO": ["2020-01-01"] * n,
            "Año": [2020] * n,
            "Autor/Dependencia": [AUTOR_DEFECTO] * n,
            "Enlace": enlaces or [f"https://www.unison.mx/nota/?idnoti={i}" for i in range(n)],
        }
    )


def test_extrae_y_clasifica_pregrado_y_posgrado():
    df = _noticias(
        [
            "Destacan estudiantes de Ingeniería Civil en concursos nacionales",
            "Concluyen su maestría en Administración 16 funcionarios públicos",
            "Otorga Unison Doctorado Honoris Causa a un investigador",
        ]
    )
    menciones, ruido = extraer_menciones(df)

    assert set(menciones["Programa"]) == {
        "Ingeniería Civil",
        "Posgrado en Administración",
    }
    assert set(menciones["Grupo"]) == {"Pregrado", "Posgrado"}
    assert "Doctorado Honoris Causa" in ruido.index


def test_alias_licenciatura_en_ingenieria_en_minas():
    df = _noticias(["Evalúan la Licenciatura en Ingeniería en Minas para reacreditación"])
    menciones, _ = extraer_menciones(df)

    assert menciones["Programa"].tolist() == ["Ingeniería en Minas"]
    assert menciones["Grupo"].tolist() == ["Pregrado"]


def test_tolera_nivel_sin_acento():
    df = _noticias(["Impulsan Maestria en Administracion en el campus"])
    menciones, _ = extraer_menciones(df)

    assert menciones["Programa"].tolist() == ["Posgrado en Administración"]
    assert menciones["Grupo"].tolist() == ["Posgrado"]


def test_posgrado_de_misma_familia_se_fusiona():
    assert resolver_mencion("Maestría en Ingeniería Industrial") == (
        "Posgrado en Ingeniería Industrial"
    )
    assert resolver_mencion("Doctorado en Ciencias en Ingeniería Industrial") == (
        "Posgrado en Ingeniería Industrial"
    )
    assert resolver_mencion("Ingeniería Industrial") == "Ingeniería Industrial y de Sistemas"
    assert es_clave_exacta("Ingeniería Industrial y de Sistemas")
    assert es_clave_exacta("Posgrado en Ciencias y Tecnología de Alimentos")


def test_lista_coordinada_se_separa_en_programas_independientes():
    partes = _menciones_de(
        "Licenciaturas",
        "Psicología y Comunicación",
        "Licenciaturas en Psicología y Comunicación",
    )
    assert partes == [
        "Licenciatura en Psicología",
        "Licenciatura en Comunicación",
    ]


def test_taxonomia_b_mantiene_mecanismo_fijo():
    from taxonomia_categorias import (
        CATEGORIA_OTROS,
        CATEGORIAS,
        TOP_N,
        UMBRAL_SIMILITUD,
    )

    assert len(CATEGORIAS) == 19
    assert CATEGORIA_OTROS == "Otros / no clasificable"
    assert UMBRAL_SIMILITUD == 0.03
    assert TOP_N == 3
    assert TOP_N >= 1


def test_una_nota_cuenta_una_vez_por_programa():
    df = _noticias(["Ingeniería Civil. Ingeniería Civil."], enlaces=["u1"])
    menciones, _ = extraer_menciones(df)

    assert len(menciones) == 1


def test_cargar_descarta_sin_fecha_y_rellena_autor(tmp_path):
    df = pd.DataFrame(
        {
            "Título": ["Ingeniería Civil", "Maestría en Administración"],
            "Fecha_ISO": ["2020-01-01", None],
            "Enlace": ["u1", "u2"],
        }
    )
    ruta = tmp_path / "noticias.parquet"
    df.to_parquet(ruta, index=False)

    limpio, descartadas = cargar_noticias(ruta)

    assert descartadas == 1
    assert len(limpio) == 1
    assert (limpio["Autor/Dependencia"] == AUTOR_DEFECTO).all()
    assert limpio["Año"].iloc[0] == 2020


def test_frecuencias_y_cobertura_del_catalogo():
    df = _noticias(
        [
            "Ingeniería Civil en concursos nacionales",
            "Ingeniería Civil en el campus Navojoa",
            "Maestría en Administración para funcionarios",
        ]
    )
    menciones, _ = extraer_menciones(df)
    freq = calcular_frecuencias(menciones, total_notas=len(df))

    civil = freq.loc[freq["Programa"] == "Ingeniería Civil", "Notas"].iloc[0]
    assert civil == 2

    cobertura = cobertura_del_catalogo(freq)
    assert len(cobertura) == len(CATALOGO)
    assert cobertura["Programa"].is_unique
    assert cobertura["Notas"].sum() == len(menciones)


def test_sin_bucles_por_filas():
    fuente = (RAIZ / "src" / "data" / "fase1_limpieza_entidades.py").read_text(encoding="utf-8")
    assert ".iterrows(" not in fuente
    assert ".itertuples(" not in fuente


def test_union_titulo_cuerpo_no_duplica_y_prefiere_titulo():
    from fase1_fulltext import unir_fuentes

    titulo = pd.DataFrame(
        {
            "Enlace": ["u1", "u2"],
            "Programa": ["Ingeniería Civil", "Licenciatura en Artes"],
            "Fuente_Mencion": ["Título", "Título"],
        }
    )
    cuerpo = pd.DataFrame(
        {
            "Enlace": ["u2"],
            "Programa": ["Licenciatura en Artes"],
            "Fuente_Mencion": ["Cuerpo"],
        }
    )

    union = unir_fuentes(titulo, cuerpo)

    assert len(union) == 2
    assert union[union["Enlace"] == "u2"]["Fuente_Mencion"].iloc[0] == "Título y cuerpo"
    assert union[union["Enlace"] == "u2"]["Programa"].iloc[0] == "Licenciatura en Artes"


def test_construir_documentos_dedup_y_trunca():
    from fase3_topicos import construir_documentos

    menciones = pd.DataFrame(
        {
            "Enlace": ["u1", "u1", "u2"],
            "Año": [2020, 2020, 2020],
            "Programa": ["A", "A", "B"],
            "Nivel": ["Licenciatura", "Licenciatura", "Licenciatura"],
            "Grupo": ["Pregrado", "Pregrado", "Pregrado"],
            "Fuente_Mencion": ["Cuerpo", "Cuerpo", "Cuerpo"],
        }
    )
    cuerpos = pd.DataFrame({"Enlace": ["u1", "u2"], "cuerpo": ["x" * 5000, "   "]})

    docs = construir_documentos(menciones, cuerpos)

    assert len(docs) == 1
    assert docs["Programa"].tolist() == ["A"]
    assert docs["Texto"].str.len().max() <= 1500


def test_topicos_por_programa_normaliza_pesos():
    from fase3_topicos import topicos_por_programa

    class ModeloFalso:
        def transform(self, matriz):
            return np.array([[1.0, 3.0], [2.0, 2.0]])

    docs = pd.DataFrame(
        {
            "Programa": ["A", "A"],
            "Nivel": ["Licenciatura", "Licenciatura"],
            "Grupo": ["Pregrado", "Pregrado"],
        }
    )

    largo = topicos_por_programa(docs, ModeloFalso(), None, 2)

    assert len(largo) == 2
    assert largo["Peso_Porcentaje"].sum() == pytest.approx(100.0, abs=0.1)
