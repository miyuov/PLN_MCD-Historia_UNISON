"""Catálogo canónico de programas académicos de la UNISON.

Fuentes:
- Licenciaturas: https://ofertaeducativa.unison.mx/ (59 programas, 2024-2026).
- Posgrados: https://www.unison.mx/posgrados/ (doctorados, maestrías y
  especialidades vigentes).

Incluye además programas históricos que ya no aparecen en la oferta vigente
pero sí en el archivo de noticias (p. ej. Licenciatura en Artes, Licenciatura
en Informática Administrativa). Conservarlos es indispensable para la Fase 2:
detectar nacimientos y declives exige no borrar la evidencia de los programas
que dejaron de ofertarse.

La normalización funciona por coincidencia de prefijo contra este catálogo:
la mención extraída por regex suele arrastrar texto posterior ("Ingeniería
Civil el Primer Foro..."), por lo que se elige la entrada canónica más larga
que sea prefijo de la mención. Lo que no coincide con el catálogo se descarta
como ruido (simposios, congresos, departamentos, campus, etc.).

El posgrado se agrupa por campo: maestría y doctorado de un mismo programa se
resuelven a una sola entrada "Posgrado en X", aunque el nombre no sea idéntico
(p. ej. "Maestría en Ingeniería Industrial" y "Doctorado en Ciencias en
Ingeniería Industrial"). Las especialidades conservan su entrada propia.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
LICENCIATURAS = [
    "Licenciatura en Administración",
    "Licenciatura en Administración Pública",
    "Licenciatura en Antropología",
    "Licenciatura en Arquitectura",
    "Licenciatura en Artes",
    "Licenciatura en Artes Escénicas",
    "Licenciatura en Artes Plásticas",
    "Licenciatura en Biología",
    "Licenciatura en Ciencias de la Computación",
    "Licenciatura en Ciencias de la Comunicación",
    "Licenciatura en Ciencias Genómicas",
    "Licenciatura en Ciencias Nutricionales",
    "Licenciatura en Contaduría Pública",
    "Licenciatura en Cultura Física y Deporte",
    "Licenciatura en Derecho",
    "Licenciatura en Diseño Gráfico",
    "Licenciatura en Economía",
    "Licenciatura en Educación",
    "Licenciatura en Enfermería",
    "Licenciatura en Enseñanza del Inglés",
    "Licenciatura en Finanzas",
    "Licenciatura en Física",
    "Licenciatura en Física Médica",
    "Licenciatura en Fisioterapia",
    "Licenciatura en Geología",
    "Licenciatura en Historia",
    "Licenciatura en Informática Administrativa",
    "Licenciatura en Lingüística",
    "Licenciatura en Literaturas Hispánicas",
    "Licenciatura en Logística",
    "Licenciatura en Matemáticas",
    "Licenciatura en Medicina",
    "Licenciatura en Mercadotecnia",
    "Licenciatura en Música",
    "Licenciatura en Negocios y Comercio Internacionales",
    "Licenciatura en Odontología",
    "Licenciatura en Psicología",
    "Licenciatura en Psicología de la Salud",
    "Licenciatura en Química",
    "Licenciatura en Químico Biólogo Clínico",
    "Licenciatura en Químico en Alimentos",
    "Licenciatura en Seguridad Pública",
    "Licenciatura en Sociología",
    "Licenciatura en Sustentabilidad",
    "Licenciatura en Trabajo Social",
    "Licenciatura en Turismo",
    "Licenciatura en Médico Veterinario Zootecnista",
]

INGENIERIAS = [
    "Ingeniería Agrónoma",
    "Ingeniería Biomédica",
    "Ingeniería Civil",
    "Ingeniería en Ciencias Ambientales",
    "Ingeniería en Energías Renovables",
    "Ingeniería en Materiales",
    "Ingeniería en Mecatrónica",
    "Ingeniería en Minas",
    "Ingeniería en Semiconductores",
    "Ingeniería en Sistemas de Información",
    "Ingeniería en Tecnología Electrónica",
    "Ingeniería Industrial y de Sistemas",
    "Ingeniería Metalúrgica",
    "Ingeniería Química",
]

MAESTRIAS = [
    "Maestría en Administración",
    "Maestría en Aduanas, Logística y Negocios Internacionales",
    "Maestría en Arquitectura",
    "Maestría en Biociencias",
    "Maestría en Bionanotecnología",
    "Maestría en Ciencia de Datos",
    "Maestría en Ciencia de Materiales",
    "Maestría en Ciencias",
    "Maestría en Ciencias Agropecuarias",
    "Maestría en Ciencias de la Ingeniería",
    "Maestría en Ciencias de la Salud",
    "Maestría en Ciencias de los Alimentos",
    "Maestría en Ciencias en Electrónica",
    "Maestría en Ciencias Geológicas",
    "Maestría en Ciencias Naturales",
    "Maestría en Ciencias Sociales",
    "Maestría en Ciencias y Tecnología de Alimentos",
    "Maestría en Comercio Exterior y Aduanas",
    "Maestría en Comunicación Estratégica",
    "Maestría en Derecho",
    "Maestría en Derecho Procesal Penal Acusatorio y Oral",
    "Maestría en Desarrollo Social",
    "Maestría en Docencia en Enseñanza Media Superior",
    "Maestría en Endocrinología Ginecológica",
    "Maestría en Enfermería de Práctica Avanzada",
    "Maestría en Enseñanza de la Historia",
    "Maestría en Enseñanza de Lenguas Extranjeras",
    "Maestría en Entrenamiento Deportivo",
    "Maestría en Finanzas",
    "Maestría en Fiscalización y Control Gubernamental",
    "Maestría en Física",
    "Maestría en Historia",
    "Maestría en Impuestos",
    "Maestría en Ingeniería Civil",
    "Maestría en Ingeniería en Internet de las Cosas",
    "Maestría en Ingeniería en Sistemas y Tecnología",
    "Maestría en Ingeniería Industrial",
    "Maestría en Ingeniería Urbana",
    "Maestría en Innovación Educativa",
    "Maestría en Integración Económica",
    "Maestría en Lingüística",
    "Maestría en Lingüística Aplicada",
    "Maestría en Literatura Hispanoamericana",
    "Maestría en Marketing y Mercados de Consumo",
    "Maestría en Matemática Educativa",
    "Maestría en Matemáticas",
    "Maestría en Nanotecnología",
    "Maestría en Políticas de Seguridad Pública",
    "Maestría en Políticas y Gestión del Desarrollo Social",
    "Maestría en Psicología",
    "Maestría en Seguridad Pública",
    "Maestría en Sistemas de Producción Agropecuaria",
    "Maestría en Sustentabilidad",
]

DOCTORADOS = [
    "Doctorado en Biociencias",
    "Doctorado en Ciencia de Materiales",
    "Doctorado en Ciencias",
    "Doctorado en Ciencias de la Ingeniería",
    "Doctorado en Ciencias de la Salud",
    "Doctorado en Ciencias de la Tierra",
    "Doctorado en Ciencias de los Alimentos",
    "Doctorado en Ciencias en Electrónica",
    "Doctorado en Ciencias en Ingeniería Industrial",
    "Doctorado en Ciencias Geológicas",
    "Doctorado en Ciencias Químico Biológicas y de la Salud",
    "Doctorado en Ciencias Sociales",
    "Doctorado en Derecho",
    "Doctorado en Electrónica",
    "Doctorado en Física",
    "Doctorado en Geociencias",
    "Doctorado en Humanidades",
    "Doctorado en Ingeniería Mecatrónica",
    "Doctorado en Innovación Educativa",
    "Doctorado en Integración Económica",
    "Doctorado en Investigación Educativa",
    "Doctorado en Matemática Educativa",
    "Doctorado en Matemáticas",
    "Doctorado en Nanotecnología",
    "Doctorado en Psicología",
]

ESPECIALIDADES = [
    "Especialidad en Análisis Clínicos",
    "Especialidad en Comercio Exterior y Aduanas",
    "Especialidad en Derecho Penal y Criminalística",
    "Especialidad en Derecho y Psicología de la Familia",
    "Especialidad en Desarrollo Sustentable",
    "Especialidad en Enfermería",
    "Especialidad en Enfermería en Cuidados Intensivos",
    "Especialidad en Enfermería Pediátrica",
    "Especialidad en Enfermería Quirúrgica Perioperatoria",
    "Especialidad en Gestión y Docencia en Enfermería",
    "Especialidad en Matemática Educativa",
]

# El posgrado se agrupa por campo: una sola entrada "Posgrado en X" por familia,
# sumando maestría y doctorado aunque el nombre no sea idéntico. Las
# especialidades conservan su entrada propia.
PREFIJOS_POSGRADO = ("Posgrado Integral en ", "Posgrado en ", "Maestría en ", "Doctorado en ")


def base_posgrado(nombre: str) -> str:
    """Devuelve el campo del posgrado, sin el nivel ni el prefijo 'Ciencias en'."""
    base = nombre
    for prefijo in PREFIJOS_POSGRADO:
        if base.startswith(prefijo):
            base = base[len(prefijo) :]
            break
    if base.startswith("Ciencias en "):
        base = base.removeprefix("Ciencias en ")
    return base


# Nombres genéricos que el corpus usa como nombre propio del posgrado.
POSGRADOS_GENERICOS = [
    "Posgrado en Biociencias",
    "Posgrado en Ciencias",
    "Posgrado en Ciencias y Tecnología de Alimentos",
    "Posgrado en Derecho",
    "Posgrado en Electrónica",
    "Posgrado en Nanotecnología",
    "Posgrado en Psicología",
    "Posgrado en Sustentabilidad",
    "Posgrado Integral en Ciencias Sociales",
]

BASES_POSGRADO = sorted(
    {base_posgrado(nombre) for nombre in MAESTRIAS + DOCTORADOS + POSGRADOS_GENERICOS}
)
POSGRADOS = [f"Posgrado en {base}" for base in BASES_POSGRADO]

# Toda maestría o doctorado se resuelve a su familia de posgrado.
MAPA_FAMILIA_POSGRADO = {
    nombre: f"Posgrado en {base_posgrado(nombre)}"
    for nombre in MAESTRIAS + DOCTORADOS + POSGRADOS_GENERICOS
}

CATALOGO = LICENCIATURAS + INGENIERIAS + ESPECIALIDADES + POSGRADOS

# ---------------------------------------------------------------------------
# Alias explícitos: variantes históricas, truncamientos y nombres antiguos.
# Clave = forma normalizada (sin acentos, minúsculas); valor = nombre canónico.
# ---------------------------------------------------------------------------
ALIASES_CRUDOS = {
    # Licenciaturas
    "Licenciatura en Comunicación": "Licenciatura en Ciencias de la Comunicación",
    "Licenciatura en Comunicación Organizacional": "Licenciatura en Ciencias de la Comunicación",
    "Licenciatura en Nutrición": "Licenciatura en Ciencias Nutricionales",
    "Licenciatura en Cultura Física y Deportes": "Licenciatura en Cultura Física y Deporte",
    "Licenciatura en Deportes": "Licenciatura en Cultura Física y Deporte",
    "Licenciatura en Enseñanza de Inglés": "Licenciatura en Enseñanza del Inglés",
    "Licenciatura en Químico Biólogo": "Licenciatura en Químico Biólogo Clínico",
    "Licenciatura en Contabilidad": "Licenciatura en Contaduría Pública",
    "Licenciatura en Químico Biólogo en Alimentos": "Licenciatura en Químico en Alimentos",
    "Licenciatura en Administración de Empresas": "Licenciatura en Administración",
    "Licenciatura en Trabajo Social Virtual": "Licenciatura en Trabajo Social",
    "Licenciatura en Trabajos Social": "Licenciatura en Trabajo Social",
    "Licenciatura en Ingeniero Agrónomo": "Ingeniería Agrónoma",
    "Licenciatura en Energías Renovables": "Ingeniería en Energías Renovables",
    "Licenciatura en Minas": "Ingeniería en Minas",
    "Licenciatura en Canto": "Licenciatura en Música",
    "Licenciatura en Danza": "Licenciatura en Artes Escénicas",
    "Licenciatura Químico Biólogo": "Licenciatura en Químico Biólogo Clínico",
    # Variantes detectadas en la Fase 1 v2 (titulares del archivo histórico).
    "Licenciatura en Ingeniería en Minas": "Ingeniería en Minas",
    # Ingenierías
    "Ingeniería Mecatrónica": "Ingeniería en Mecatrónica",
    "Licenciatura en Mecatrónica": "Ingeniería en Mecatrónica",
    "Ingeniería en Sistemas de la Información": "Ingeniería en Sistemas de Información",
    "Ingeniería en Tecnología en Electrónica": "Ingeniería en Tecnología Electrónica",
    "Ingeniería Electrónica": "Ingeniería en Tecnología Electrónica",
    "Ingeniería Industrial y Sistemas": "Ingeniería Industrial y de Sistemas",
    "Ingeniería Industrial": "Ingeniería Industrial y de Sistemas",
    "Ingeniería Agrónomo": "Ingeniería Agrónoma",
    "Ingeniería Minera": "Ingeniería en Minas",
    "Ingeniería Minero": "Ingeniería en Minas",
    "Ingeniería Metalurgia": "Ingeniería Metalúrgica",
    # Maestrías
    "Maestría en Literatura": "Maestría en Literatura Hispanoamericana",
    "Maestría en Literaturas Hispanoamericanas": "Maestría en Literatura Hispanoamericana",
    "Maestría en Ciencias de Datos": "Maestría en Ciencia de Datos",
    "Maestría en Ciencias de los Materiales": "Maestría en Ciencia de Materiales",
    "Maestría en Ciencia de Datos en Italia": "Maestría en Ciencia de Datos",
    "Maestría en Internet de las Cosas": "Maestría en Ingeniería en Internet de las Cosas",
    "Maestría en Matemáticas Educativa": "Maestría en Matemática Educativa",
    "Maestría en Matemáticas Educativas": "Maestría en Matemática Educativa",
    "Maestría en Comercio Exterior": "Maestría en Comercio Exterior y Aduanas",
    "Maestría en Procedimiento Penal Acusatorio y Oral": (
        "Maestría en Derecho Procesal Penal Acusatorio y Oral"
    ),
    "Maestría en Derecho Procesal, Penal Acusatorio y Oral": (
        "Maestría en Derecho Procesal Penal Acusatorio y Oral"
    ),
    "Maestría en Procedimiento Penal, Acusatorio y Oral": (
        "Maestría en Derecho Procesal Penal Acusatorio y Oral"
    ),
    "Maestría en Derecho Procesal en Campus Navojoa": "Maestría en Derecho Procesal Penal Acusatorio y Oral",
    # Doctorados
    "Doctorado en Ciencias de Materiales": "Doctorado en Ciencia de Materiales",
    "Doctorado en Ciencias de los Materiales": "Doctorado en Ciencia de Materiales",
    "Doctorado en Ciencias Químico Biológicas": (
        "Doctorado en Ciencias Químico Biológicas y de la Salud"
    ),
    "Doctorado en Ciencia en Ingeniería Industrial": (
        "Doctorado en Ciencias en Ingeniería Industrial"
    ),
    "Doctorado en Ciencias en Ingeniería Industrial": (
        "Doctorado en Ciencias en Ingeniería Industrial"
    ),
    # Especialidades
    "Especialidad en Derecho Penal y Criminología y en Derecho y Psicología de la Familia": (
        "Especialidad en Derecho Penal y Criminalística"
    ),
    "Posgrado en Derecho y Psicología de la Familia": (
        "Especialidad en Derecho y Psicología de la Familia"
    ),
    # Posgrados genéricos -> programa concreto (solo cuando NO existe una
    # entrada propia "Posgrado en X" en el catálogo).
    "Posgrado en Administración": "Maestría en Administración",
    "Posgrado en Alimentos": "Posgrado en Ciencias y Tecnología de Alimentos",
    "Posgrado en Ciencias de la Salud": "Maestría en Ciencias de la Salud",
    "Posgrado en Ciencias del Departamento de Investigación en Física": "Maestría en Física",
    "Posgrado en Ciencias en Electrónica": "Posgrado en Electrónica",
    "Posgrado en Ciencias Matemáticas": "Maestría en Matemáticas",
    "Posgrado en Ciencias Sociales": "Posgrado Integral en Ciencias Sociales",
    "Posgrado Integral de Ciencias Sociales": "Posgrado Integral en Ciencias Sociales",
    "Posgrado en Desarrollo Social": "Maestría en Desarrollo Social",
    "Posgrado en Física": "Maestría en Física",
    "Posgrado en Ingeniería Civil": "Maestría en Ingeniería Civil",
    "Posgrado en Ingeniería Industrial": "Maestría en Ingeniería Industrial",
    "Posgrado en Innovación Educativa": "Maestría en Innovación Educativa",
    "Posgrado en Integración Económica": "Maestría en Integración Económica",
    "Posgrado en Maestría en Ingeniería Urbana": "Maestría en Ingeniería Urbana",
    "Posgrado Maestría en Ingeniería Urbana": "Maestría en Ingeniería Urbana",
    "Posgrado en Matemática Educativa": "Maestría en Matemática Educativa",
    "Posgrado en Matemáticas": "Maestría en Matemáticas",
    "Posgrado en Ciencia y Tecnología de Alimentos": (
        "Posgrado en Ciencias y Tecnología de Alimentos"
    ),
    "Posgrado en Ciencias y Tecnología en Alimentos": (
        "Posgrado en Ciencias y Tecnología de Alimentos"
    ),
    # Maestrías que en el corpus aparecen bajo el nombre genérico del posgrado.
    "Maestría en Sustentabilidad": "Posgrado en Sustentabilidad",
    "Maestría en Psicología": "Posgrado en Psicología",
    "Maestría en Biociencias": "Posgrado en Biociencias",
    "Maestría en Nanotecnología": "Posgrado en Nanotecnología",
    "Maestría en Alimentos": "Posgrado en Ciencias y Tecnología de Alimentos",
    "Maestría en Ciencias y Tecnología de Alimentos": (
        "Posgrado en Ciencias y Tecnología de Alimentos"
    ),
}


def normalizar_clave(texto: str) -> str:
    """Minúsculas, sin acentos y sin puntuación, para comparar entidades."""
    limpio = unicodedata.normalize("NFKD", str(texto))
    limpio = limpio.encode("ascii", "ignore").decode("utf-8").lower()
    limpio = re.sub(r"[,.;:()]", " ", limpio)
    return re.sub(r"\s+", " ", limpio).strip()


def normalizar_claves(texto: pd.Series) -> pd.Series:
    """Versión vectorizada de :func:`normalizar_clave`."""
    return (
        texto.astype("string")
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("utf-8")
        .str.lower()
        .str.replace(r"[,.;:()]", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


CATALOGO_POR_CLAVE = {normalizar_clave(nombre): nombre for nombre in CATALOGO}
ALIASES_CRUDOS.update(MAPA_FAMILIA_POSGRADO)
ALIASES = {
    normalizar_clave(clave): MAPA_FAMILIA_POSGRADO.get(valor, valor)
    for clave, valor in ALIASES_CRUDOS.items()
}
RESOLUBLES = {**CATALOGO_POR_CLAVE, **ALIASES}


def _resolver(clave: str) -> str | None:
    if clave in RESOLUBLES:
        return RESOLUBLES[clave]

    # La mención puede arrastrar texto posterior: se queda con la entrada
    # canónica (o alias) más larga que sea prefijo exacto con frontera de
    # palabra.
    candidatos = [resoluble for resoluble in RESOLUBLES if clave.startswith(resoluble + " ")]
    if candidatos:
        return RESOLUBLES[max(candidatos, key=len)]
    return None


def mapear_claves(claves: pd.Series) -> pd.Series:
    """Resuelve cada mención contra el catálogo. Devuelve NaN si es ruido."""
    unicas = pd.unique(claves.dropna())
    mapa = {clave: _resolver(clave) for clave in unicas}
    return claves.map(mapa)


def es_clave_exacta(mencion: str) -> bool:
    """Indica si la mención completa ya es un programa o alias conocido.

    Sirve para no partir nombres oficiales que contienen 'y', como
    'Ingeniería Industrial y de Sistemas' o 'Ciencias y Tecnología de Alimentos'.
    """
    return normalizar_clave(mencion) in RESOLUBLES


def resolver_mencion(mencion: str) -> str | None:
    """Resuelve una mención suelta; devuelve None si no es un programa."""
    return _resolver(normalizar_clave(mencion))
