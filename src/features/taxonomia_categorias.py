"""Taxonomía fija de categorías temáticas para la capa B+.

Cada categoría se describe con un vocabulario controlado en español. La
asignación se hace por similitud coseno entre el TF-IDF de la nota y el de la
descripción, de modo que el método compara contra temas propuestos (a
diferencia de NMF, que los descubre).

Las categorías se eligieron con cuatro criterios: presencia en el corpus
(>1% de las notas), interpretabilidad, cobertura de la actividad y no
duplicación con los tópicos de NMF. `Otros / no clasificable` recoge las notas
cuya similitud máxima no alcanza el umbral.
"""

from __future__ import annotations

CATEGORIAS: dict[str, str] = {
    "Admisión e ingreso": (
        "examen admisión ingreso aspirantes convocatoria inscripción nuevo ingreso "
        "ceneval puntaje ficha cupo registro"
    ),
    "Oferta educativa y docencia": (
        "plan estudios currículo acreditación reacreditación evaluación educativa "
        "docencia profesores enseñanza aprendizaje calidad educativa posgrado "
        "licenciatura carrera"
    ),
    "Investigación y ciencia": (
        "investigación científica laboratorio proyecto científico descubrimiento "
        "publicación artículo ciencia tecnología conocimiento investigadores"
    ),
    "Salud y medicina": (
        "salud medicina médicos pacientes clínica enfermedad atención médica hospital "
        "diagnóstico tratamiento prevención nutrición enfermería psicología"
    ),
    "Artes y cultura": (
        "arte música danza teatro exposición cultura libro poesía pintura cine "
        "concierto obra artística festival cultural"
    ),
    "Deportes": (
        "deporte deportivo atletismo medalla campeonato torneo judo voleibol "
        "fútbol basquetbol entrenamiento búhos competencia"
    ),
    "Infraestructura y campus": (
        "obra construcción edificio campus inauguración remodelación instalaciones "
        "aulas laboratorios infraestructura terreno"
    ),
    "Vinculación y sector productivo": (
        "convenio vinculación empresa sector productivo colaboración acuerdo "
        "industria cooperación alianza prácticas"
    ),
    "Reconocimientos y premios": (
        "premio reconocimiento distinción galardón honor mérito trayectoria "
        "homenaje destacado"
    ),
    "Eventos académicos y congresos": (
        "congreso simposio foro conferencia semana encuentro jornada taller "
        "coloquio seminario evento"
    ),
    "Egresados y graduación": (
        "egresado titulación graduación ceremonia generación pasante título "
        "profesionistas graduados"
    ),
    "Sustentabilidad y medio ambiente": (
        "sustentable sustentabilidad ambiental medio ambiente agua energía "
        "cambio climático ecología reciclaje"
    ),
    "Derechos, género e inclusión": (
        "género igualdad derechos humanos inclusión violencia diversidad "
        "discriminación equidad"
    ),
    "Tecnología e innovación": (
        "tecnología innovación digital software inteligencia artificial datos "
        "sistemas computación robótica internet"
    ),
    "Gobierno universitario": (
        "rector rectoría consejo universitario sindicato presupuesto "
        "administración universitaria huelga"
    ),
    "Derecho y justicia": (
        "derecho penal justicia jurídico abogados tribunal acusatorio leyes "
        "criminología legal"
    ),
    "Divulgación y medios": (
        "radio televisión difusión divulgación revista periódico medios "
        "comunicación transmisión"
    ),
    "Internacionalización y movilidad": (
        "internacional movilidad intercambio extranjero convenio internacional "
        "estudiantes foráneos universidad extranjera"
    ),
    "Agropecuario y alimentos": (
        "agrícola agropecuario ganadería campo cultivo cosecha alimentos "
        "veterinaria zootecnia"
    ),
}

CATEGORIA_OTROS = "Otros / no clasificable"
UMBRAL_SIMILITUD = 0.03
TOP_N = 3
