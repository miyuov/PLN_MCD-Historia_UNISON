# Análisis de Cobertura Mediática Institucional (UNISON)

## Descripción del Proyecto

Este proyecto de Procesamiento de Lenguaje Natural (PLN) analiza el histórico de noticias de la
Universidad de Sonora (UNISON) para investigar la representación mediática de sus programas
académicos. El objetivo es identificar qué programas (licenciaturas, ingenierías, posgrados)
tienen mayor protagonismo en el discurso oficial, cuáles sufren de "olvido mediático" y cuáles
son los tópicos narrativos asociados a ellos.

**Fuente oficial:** [https://www.unison.mx/noticias-anteriores/](https://www.unison.mx/noticias-anteriores/)

## Corpus y artefactos

| Artefacto | Registros | Descripción |
|---|---:|---|
| `data/raw/noticias_raw_full.parquet` | 37,975 | Corpus completo del portal histórico (2003–2026), deduplicado por `Enlace`. |
| `data/raw/noticias_raw.parquet` | 2,841 | Muestra equilibrada: máximo 10 notas por mes. |
| `data/raw/noticias_relevantes.parquet` | 1,952 | Notas con programa académico o lenguaje de admisión/oferta. |
| `data/interim/corpus_analisis.parquet` | 37,882 | Corpus analizable: notas internas con patrón `/nota/?idnoti=`, ventana 2003–2026, deduplicadas por enlace. |
| `data/interim/cuerpos_noticias.parquet` | 1,952 | Cuerpos descargados sobre el subconjunto relevante. |
| `data/interim/cuerpos_full.parquet` | 37,882 | Cuerpos completos: 100% de cobertura, 95.35 M caracteres. |
| `data/interim/noticias_limpias.parquet` | 1,486 | Menciones catalogadas desde títulos. |
| `data/interim/noticias_limpias_full.parquet` | 22,403 | Menciones catalogadas desde título + cuerpo. |
| `src/features/catalogo_programas.py` | 131 | Catálogo canónico: 47 licenciaturas, 14 ingenierías, 11 especialidades y 59 familias de posgrado. |

**Calidad del corpus:** de 37,975 filas, 93 enlaces no son notas periodísticas y quedan fuera del
corpus analizable. Tras ese filtro quedan 37,882 notas internas. De esas, 12 tienen título vacío
o "." y se conservan porque su cuerpo sí aporta texto. La ventana temporal es 2003–2026.

**Catálogo:** maestría y doctorado de un mismo programa se agrupan en una sola entrada
`Posgrado en X`, aunque el nombre no sea idéntico. Las especialidades conservan su entrada
propia. "Ingeniería Industrial" se resuelve a "Ingeniería Industrial y de Sistemas".

## Metodología

El análisis se realiza mediante un pipeline estructurado (Cookiecutter Data Science) que prioriza
la eficiencia computacional (bajo consumo de memoria y tokens).

1. **Extracción y limpieza:** identificación de entidades académicas en títulos y cuerpos mediante
   expresiones regulares vectorizadas y normalización contra un catálogo canónico. Cada mención se
   clasifica por nivel (Pregrado/Posgrado). Las listas coordinadas ("Psicología y Comunicación")
   se separan en programas independientes cuando cada parte resuelve contra el catálogo.
2. **Cuantificación:** frecuencias absolutas y relativas para medir la "Brecha de Visibilidad"
   entre niveles a lo largo del tiempo, el índice de olvido y la concentración de la cobertura.
3. **Descubrimiento de tópicos:** NMF (*Non-negative Matrix Factorization*) sobre TF-IDF para
   descubrir las temáticas asociadas a los programas. Se eligió NMF frente a LDA porque, con la
   prosa institucional homogénea del corpus, LDA colapsó casi todos los documentos en un solo
   tópico "académico/investigación"; NMF produce tópicos disjuntos e interpretables con el mismo
   costo computacional (sin GPU ni embeddings). Se reportan top-3 y coherencia NPMI.
4. **Clasificación temática B+:** taxonomía fija de 19 categorías descritas con vocabulario
   controlado, más `Otros / no clasificable`. Cada nota se compara contra las descripciones por
   similitud coseno sobre el TF-IDF del corpus; si la similitud máxima no alcanza 0.03, cae en
   `Otros`. Se persiste categoría principal y top-3. B+ complementa a NMF: NMF descubre temas,
   B+ los verifica con un marco estable.

**Nota metodológica sobre spaCy:** la Fase 1 se resolvió con `pandas` + `regex` porque el patrón
taxonómico es determinista y el catálogo canónico ya contiene las variantes históricas. spaCy no
está instalado en el entorno y no fue necesario para las fases 2–3.

## Estado del Pipeline

- [x] **Fase 1 (título):** 37,975 notas → 1,403 con programa, 1,486 menciones. PC1 validado.
- [x] **Fase 1 (full-text):** 37,882 notas → 15,386 con programa (40.62%), 22,403 menciones. PC1
  full-text validado.
- [x] **Fase 2 (full-text):** cobertura, brecha Pregrado/Posgrado, olvido, evolución y
  concentración. PC2 validado; métricas en `data/processed/`.
- [x] **Fase 3 (tópicos):** NMF/TF-IDF sobre 22,403 menciones; 15 tópicos, 129 programas. PC3
  generado; artefactos en `data/processed/`.
- [x] **Fase 3 (B+):** 19 categorías + `Otros`, umbral 0.03, top-1 y top-3 por nota y programa.
- [x] **Fase 4 (narrativa):** reporte en tres actos y siete figuras. PC4 pendiente de validación.

---

## Fase 1 — Título (PC1 histórico)

**Script:** `src/data/fase1_limpieza_entidades.py`. **Salida:** `data/interim/noticias_limpias.parquet` (validado).

| Indicador | Valor |
|---|---:|
| Notas analizadas | 37,975 |
| Notas con al menos un programa | 1,403 (3.69%) |
| Menciones catalogadas | 1,486 |
| Programas observados | 126 de 131 |
| Ruido descartado | 218 menciones (123 etiquetas) |

| # | Programa | Grupo | Notas |
|---:|---|---|---:|
| 1 | Ingeniería Industrial y de Sistemas | Pregrado | 103 |
| 2 | Ingeniería Civil | Pregrado | 102 |
| 3 | Posgrado en Administración | Posgrado | 50 |
| 4 | Ingeniería Química | Pregrado | 49 |
| 5 | Ingeniería en Minas | Pregrado | 45 |
| 6 | Licenciatura en Derecho | Pregrado | 42 |
| 7 | Licenciatura en Medicina | Pregrado | 40 |
| 8 | Licenciatura en Música | Pregrado | 39 |
| 9 | Posgrado en Derecho | Posgrado | 38 |
| 10 | Posgrado en Innovación Educativa | Posgrado | 38 |

**Lectura:** en los titulares dominan Ingeniería Industrial y de Sistemas (103) e Ingeniería
Civil (102), y Pregrado acumula 65.2% de las menciones. Este resultado mide la agenda editorial
del titular, no la cobertura completa.

---

## Fase 1 — Full-text: título + cuerpo (PC1 validado)

**Script:** `src/data/fase1_fulltext.py`. **Salida:** `data/interim/noticias_limpias_full.parquet`.

| Indicador | Valor |
|---|---:|
| Corpus analizable | 37,882 notas |
| Cuerpos válidos | 37,882 (100%) |
| Notas con programa (título) | 1,403 |
| Notas con programa (cuerpo) | 15,314 |
| Notas con programa (unión) | **15,386 (40.62%)** |
| Menciones (unión) | **22,403** |
| Programas observados | 129 de 131 |

**Top 10 (unión título + cuerpo):**

| # | Programa | Grupo | Notas |
|---:|---|---|---:|
| 1 | Ingeniería Industrial y de Sistemas | Pregrado | 1,504 |
| 2 | Licenciatura en Derecho | Pregrado | 1,112 |
| 3 | Licenciatura en Ciencias de la Comunicación | Pregrado | 1,025 |
| 4 | Ingeniería Civil | Pregrado | 958 |
| 5 | Ingeniería Química | Pregrado | 818 |
| 6 | Posgrado en Ciencias y Tecnología de Alimentos | Posgrado | 752 |
| 7 | Licenciatura en Psicología | Pregrado | 716 |
| 8 | Licenciatura en Música | Pregrado | 712 |
| 9 | Licenciatura en Artes | Pregrado | 688 |
| 10 | Licenciatura en Medicina | Pregrado | 613 |

**Lectura:** el cuerpo transforma el ranking. El programa más mencionado es **Ingeniería
Industrial y de Sistemas (1,504)**; el volumen de notas con programa pasa de 3.69% (títulos) a
40.62% (texto completo).

---

## Fase 2 — Cobertura y brecha mediática (PC2 validado)

**Script:** `src/data/fase2_cobertura_brecha.py`. **Artefactos:** `cobertura_programas`,
`brecha_nivel`, `cobertura_anual`, `evolucion_nivel`, `olvido_mediatico`, `concentracion`,
`resumen_pc2` (todos en `data/processed/`). **Libreta:** `notebooks/04_cobertura_y_brecha.ipynb`.

### Brecha Pregrado / Posgrado

| Grupo | Programas | Activos | Notas | % Cobertura | Menciones | % Menciones |
|---|---:|---:|---:|---:|---:|---:|
| Pregrado | 61 | 61 | 12,633 | 33.35% | 17,763 | 79.29% |
| Posgrado | 70 | 68 | 3,889 | 10.27% | 4,640 | 20.71% |

- **Brecha de participación:** +58.58 puntos porcentuales a favor de Pregrado.
- **Brecha de cobertura:** +23.08 puntos porcentuales (33.35% vs. 10.27% del total de 37,882 notas).
- **Razón de cobertura:** 3.25 notas de Pregrado por cada nota de Posgrado.
- **Promedio por programa activo:** 291.2 notas (Pregrado) vs. 68.2 (Posgrado).

### Olvido mediático

- Cuartil inferior: ≤ 18 notas. **34 programas olvidados** (26.0% del catálogo).
- **2 programas sin ninguna mención**, **2 con mención única** y **30 con cobertura muy baja**;
  **31 de los 34 olvidados son de Posgrado**.
- Los dos programas sin mención son la Especialidad en Enfermería Pediátrica y la Especialidad en
  Enfermería Quirúrgica Perioperatoria.

### Evolución temporal (menciones por 1,000 notas)

| Década | Pregrado | Posgrado |
|---|---:|---:|
| 2000s | 280.04 | 77.26 |
| 2010s | 327.19 | 101.57 |
| 2020s | 398.11 | 129.37 |

La cobertura crece en ambos niveles, pero la brecha se amplía: de 202.8 a 268.7 puntos por 1,000.
El Pregrado parte de una base 3.6 veces mayor.

### Concentración

| Métrica | Valor |
|---|---:|
| Participación Top 1 | 6.71% |
| Participación Top 5 | 24.18% |
| Participación Top 10 | 39.72% |
| Participación Top 20 | 60.17% |
| Participación Top 50 | 87.88% |
| HHI | 244.9 |
| Gini | 0.661 |

---

## Fase 3 — Modelado de tópicos por programa (PC3)

**Script:** `src/data/fase3_topicos.py`. **Libreta:** `notebooks/05_topicos.ipynb`.
**Artefactos:** `topicos_programas.parquet`, `topicos_definicion.parquet`,
`topicos_nivel.parquet` y `resumen_pc2.parquet` (tópico principal y top-3).

**Configuración:** NMF con 15 componentes, TF-IDF sublineal, semilla `20261103`. La unidad
documental es la mención (`Enlace`, `Programa`), usando el cuerpo de la nota. El tópico principal
de un programa es el de mayor carga acumulada en sus menciones. La coherencia se mide con NPMI
sobre la matriz binaria documento-término.

### Tópicos descubiertos

| Tema | Etiqueta | Palabras clave | Coherencia | Programas |
|---:|---|---|---:|---:|
| 1 | Sociedad y vida universitaria | ser / vida / cómo / rubio / sociedad | 0.069 | 3 |
| 2 | Premios y trayectorias | premio / trayectoria / estudiantil / rectora / 2023 | 0.270 | 2 |
| 3 | Artes, música y danza | artes / música / danza / bellas / teatro | 0.339 | 4 |
| 4 | Salud y enfermería | salud / enfermería / medicina / módulos / atención | 0.245 | 7 |
| 5 | Admisión e ingreso | aspirantes / ingreso / examen / convocatoria / registro | 0.393 | 9 |
| 6 | Gobierno universitario | rector / ortega / romero / grijalva / monteverde | 0.350 | 5 |
| 7 | Alimentos y nutrición | alimentos / dipa / alimentación / radio / tiempo | 0.310 | 7 |
| 8 | Calidad y evaluación educativa | acreditación / evaluación / calidad / consejo / educación | 0.273 | 5 |
| 9 | Eventos académicos | evento / conferencias / actividades / congreso / semana | 0.161 | 11 |
| 10 | Egreso y graduación | ceremonia / egresados / generación / graduantes / pasante | 0.326 | 5 |
| 11 | Divulgación científica | feria / biociencias / 12 / 13 / biológicas | 0.109 | 9 |
| 12 | Vida estudiantil y movilidad | semestre / física / concurso / segundo / movilidad | 0.087 | 10 |
| 13 | Ingeniería y tecnología | industrial / química / sistemas / materiales / civil | 0.230 | 26 |
| 14 | Derecho y ciencias sociales | derecho / curso / comunicación / sociales / psicología | 0.131 | 22 |
| 15 | Unidades regionales | unidad / regional / norte / caborca / urn | 0.360 | 4 |

Coherencia NPMI media: **0.244**. Diversidad de términos: **0.95**.

### Tópico principal de los programas más visibles

| Programa | Grupo | Notas | Tópico principal | Peso (%) |
|---|---|---:|---|---:|
| Ingeniería Industrial y de Sistemas | Pregrado | 1,504 | Ingeniería y tecnología | 19.00 |
| Licenciatura en Derecho | Pregrado | 1,112 | Derecho y ciencias sociales | 23.11 |
| Licenciatura en Ciencias de la Comunicación | Pregrado | 1,025 | Derecho y ciencias sociales | 20.29 |
| Ingeniería Civil | Pregrado | 958 | Ingeniería y tecnología | 18.65 |
| Ingeniería Química | Pregrado | 818 | Ingeniería y tecnología | 25.68 |
| Posgrado en Ciencias y Tecnología de Alimentos | Posgrado | 752 | Alimentos y nutrición | 49.70 |
| Licenciatura en Psicología | Pregrado | 716 | Derecho y ciencias sociales | 19.42 |
| Licenciatura en Música | Pregrado | 712 | Artes, música y danza | 51.32 |
| Licenciatura en Artes | Pregrado | 688 | Artes, música y danza | 57.25 |
| Licenciatura en Medicina | Pregrado | 613 | Salud y enfermería | 19.39 |
| Licenciatura en Artes Escénicas | Pregrado | 532 | Artes, música y danza | 52.49 |
| Licenciatura en Administración | Pregrado | 524 | Egreso y graduación | 15.14 |

### Perfil temático por nivel (peso medio)

| Tema | Pregrado | Posgrado |
|---|---:|---:|
| 1. Sociedad y vida universitaria | 0.08 | 0.11 |
| 2. Premios y trayectorias | 0.04 | 0.02 |
| 3. Artes, música y danza | **0.10** | 0.02 |
| 4. Salud y enfermería | **0.06** | 0.03 |
| 5. Admisión e ingreso | 0.05 | 0.05 |
| 6. Gobierno universitario | 0.07 | 0.06 |
| 7. Alimentos y nutrición | 0.03 | **0.14** |
| 8. Calidad y evaluación educativa | 0.05 | 0.06 |
| 9. Eventos académicos | 0.09 | 0.09 |
| 10. Egreso y graduación | **0.07** | 0.03 |
| 11. Divulgación científica | 0.04 | 0.05 |
| 12. Vida estudiantil y movilidad | **0.11** | 0.09 |
| 13. Ingeniería y tecnología | 0.09 | 0.09 |
| 14. Derecho y ciencias sociales | 0.09 | **0.12** |
| 15. Unidades regionales | **0.06** | 0.04 |

**Lecturas:**

1. **Derecho** se asocia a un tópico jurídico-social nítido (23.1%; 46.0% en el Posgrado en
   Derecho), lo que sugiere una narración especializada y no solo de eventos institucionales.
2. **Artes y Música** se asocian a un tópico cultural nítido (51–57% de su carga temática), el
   más especializado del Pregrado.
3. **Alimentos (Posgrado)** es el caso de mayor especialización (49.7%) y explica que el Posgrado
   quintuplique al Pregrado en el tópico de alimentos (0.14 vs. 0.03).
4. **Ingenierías** comparten el tópico técnico-industrial (T13), lo que refleja una narrativa
   común de proyectos, materiales y sistemas.
5. **Comunicación, Psicología y Administración** presentan tópicos más dispersos (15–20%), señal
   de una cobertura menos especializada.

---

## Fase 3 — Capa B+ de categorías temáticas

**Script:** `src/data/fase3_taxonomia.py`. **Taxonomía:** `src/features/taxonomia_categorias.py`.
**Artefactos:** `categorias_notas.parquet`, `categorias_programas.parquet`,
`categorias_definicion.parquet` y columnas de categoría en `resumen_pc2.parquet`.

| Indicador | Valor |
|---|---:|
| Categorías | 19 + `Otros / no clasificable` |
| Umbral de similitud | 0.03 |
| Notas clasificadas | 15,386 |
| Notas con categoría | 13,548 (88.05%) |
| Notas en `Otros` | 1,838 (11.95%) |
| Programas con categoría | 129 |

**Distribución global (top 8):**

| Categoría | Notas | % |
|---|---:|---:|
| Otros / no clasificable | 1,838 | 11.95 |
| Artes y cultura | 1,836 | 11.93 |
| Oferta educativa y docencia | 1,376 | 8.94 |
| Eventos académicos y congresos | 1,286 | 8.36 |
| Salud y medicina | 1,180 | 7.67 |
| Investigación y ciencia | 997 | 6.48 |
| Sustentabilidad y medio ambiente | 850 | 5.52 |
| Vinculación y sector productivo | 701 | 4.56 |

**Lectura:** las categorías dominantes coinciden con los tópicos NMF de mayor peso (artes,
docencia, eventos, salud, investigación), pero B+ permite comparar notas y programas con un marco
fijo. `Otros` no es ruido: agrupa notas sin similitud suficiente con las descripciones.

---

## Fase 4 — Narrativa en tres actos (PC4)

**Reporte:** [`reports/fase4_narrativa.md`](../reports/fase4_narrativa.md). **Script de figuras:**
`src/data/fase4_narrativa.py`. **Salida:** `reports/figures/fig01`–`fig07`.

| Acto | Pregunta | Evidencia |
|---|---|---|
| I. Estatus quo | ¿Quién acapara el micrófono? | Top 20 (60.17% de menciones), brecha de participación de 58.58 pp, 34 programas olvidados (31 de Posgrado). |
| II. Evolución | ¿Cómo cambia la agenda? | Tasas por década, picos 2025 (Pregrado) y 2021 (Posgrado), trayectorias Música/Psicología/Artes/Alimentos. |
| III. Discurso | ¿De qué se habla? | 15 tópicos NMF con coherencia NPMI, top-3 por programa, perfil temático por nivel y capa B+ de categorías. |

**Figuras:** `fig01_top20_cobertura`, `fig02_brecha_nivel`, `fig03_evolucion_nivel`,
`fig04_topicos_nivel`, `fig05_topicos_top_programas`, `fig06_olvido_mediatico`,
`fig07_categorias`.

**Hallazgo central:** el olvido mediático es estructural y casi exclusivo del Posgrado (31 de 34
programas del cuartil inferior); dos especialidades no recibieron una sola mención en 23 años.

**Libreta de entrega:** [`notebooks/07_historia.ipynb`](../notebooks/07_historia.ipynb).

---

## Libreta de entrega (Actividad 1)

**Libreta:** [`notebooks/07_historia.ipynb`](../notebooks/07_historia.ipynb).

Cuaderno de cierre de la **Actividad 1 — Análisis de noticias de la Universidad**. Resume el
recorrido completo del pipeline (scraping → deduplicación → corpus → cuerpos → menciones →
cobertura → tópicos → clasificación temática → narrativa), muestra las métricas finales, incluye
la evaluación de la presencia de posgrado por año y expone las figuras que sostienen la historia.
Complementa al **Punto de Control 4** y al reporte de Fase 4.

---

## Auditoría de datos (solo lectura)

**Libreta:** [`notebooks/06_auditoria_datos.ipynb`](../notebooks/06_auditoria_datos.ipynb).

Recorre el linaje completo —crudo → corpus → cuerpos → menciones → cobertura → tópicos →
narrativa— con valores esperados, `asserts`, muestras y un diagnóstico final. **No descarga ni
sobrescribe datos**; es una checklist ejecutable antes de regenerar el snapshot.

Observaciones conocidas que la libreta documenta:

- El crudo se deduplicó por `Enlace`: 37,985 → 37,975 filas; los 10 registros retirados eran
  enlaces externos/no-nota sin efecto en las métricas.
- La muestra histórica `noticias_raw.parquet` tiene 1 enlace malformado y no se usa para métricas
  finales.
- 12 títulos inválidos conservados por el cuerpo.
- 10 cuerpos de ≤50 caracteres (fecha + punto).
- Las notas por nivel no son aditivas: 16,522 vs. 15,386 notas únicas.
- `cobertura_anual` omite combinaciones con cero menciones.
- 2026, 2020s y 2025–2029 son periodos parciales.

---

## Limitaciones

- **Cuerpo como contexto:** el tópico describe la nota en que se menciona al programa, no la
  esencia del programa; una nota puede tratar otro tema y mencionar al programa de pasada.
- **Tópico principal ≠ tópico único:** los pesos son participaciones sobre 15 temas; valores de
  13–26% indican cobertura temática dispersa, no ausencia de tema.
- **Vocabulario:** sin lematización ni reconocimiento de entidades (spaCy no disponible), quedan
  nombres propios y variantes en las palabras clave (p. ej. "rubio", "ortega").
- **Departamento como proxy:** expresiones como `Departamento de Ingeniería Civil y Minas` se
  contabilizan como mención del programa.
- **Umbral B+:** 0.03 es una decisión operativa; un umbral más alto reduciría la cobertura y
  aumentaría `Otros`; uno más bajo asignaría categorías a notas de similitud débil.
- **2026 es parcial:** el corpus termina en octubre de 2026; no se usa para conclusiones de
  tendencia.

---

## Reproducibilidad

### Preparación del entorno

```powershell
# Instala las dependencias y crea el entorno (.venv) con uv
uv sync
```

### Pipeline de datos y resultados

```powershell
# Fase 1 full-text (PC1)
uv run python -X utf8 src/data/fase1_fulltext.py --corpus data/interim/corpus_analisis.parquet --cuerpos data/interim/cuerpos_full.parquet

# Persistir tras validación
uv run python -X utf8 src/data/fase1_fulltext.py --corpus data/interim/corpus_analisis.parquet --cuerpos data/interim/cuerpos_full.parquet --guardar

# Fase 2 (PC2)
uv run python -X utf8 src/data/fase2_cobertura_brecha.py --input data/interim/noticias_limpias_full.parquet --corpus data/interim/corpus_analisis.parquet

# Fase 3 (PC3): tópicos NMF
uv run python -X utf8 src/data/fase3_topicos.py

# Fase 3: clasificación temática por similitud coseno
uv run python -X utf8 src/data/fase3_taxonomia.py

# Fase 4 (PC4): figuras de la narrativa
uv run python -X utf8 src/data/fase4_narrativa.py
```

### Ejecución de las libretas

Las libretas usan rutas relativas (`../data`, `../reports`), por lo que deben
ejecutarse con el directorio de trabajo en `notebooks/`. El siguiente comando
las ejecuta en orden, actualiza sus salidas y se detiene si alguna celda falla:

```powershell
uv run python -X utf8 src/features/ejecutar_libretas.py
```

También puede ejecutarse con `make notebooks` o abrirlas interactivamente:

```powershell
uv run jupyter lab
```

Orden de las libretas:

| Libreta | Contenido |
|---|---|
| `notebooks/04_cobertura_y_brecha.ipynb` | Cobertura, brecha, olvido y concentración |
| `notebooks/05_topicos.ipynb` | Tópicos NMF y clasificación temática |
| `notebooks/06_auditoria_datos.ipynb` | Auditoría de artefactos y cifras esperadas |
| `notebooks/07_historia.ipynb` | Historia de entrega (Actividad 1) |

### Verificación

```powershell
uv run pytest -q
uv run ruff check .
```

## Próximos pasos

1. Validar el Punto de Control 4 (narrativa y figuras); si no convence, revertir al snapshot
   `checkpoint_2026-11-03_v2_fase3.zip`.
2. Tras la validación, regenerar el snapshot con `reports/fase4_narrativa.md` y las figuras.
3. Redactar el resumen ejecutivo final / conclusiones del proyecto.
