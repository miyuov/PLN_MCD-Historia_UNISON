# Pipeline de Ejecución NLP para Análisis de Cobertura Mediática Institucional

Este documento define el flujo de trabajo interactivo que el agente de IA debe seguir para procesar el histórico de noticias de la UNISON. El agente deberá adoptar los Skills definidos secuencialmente, actualizar la documentación y detenerse en cada punto de control para minimizar el consumo de tokens y asegurar la calidad.

## Entorno Tecnológico y Enfoque
- Lenguaje: Python (Jupyter Notebook / Terminal).
- Manejo de Paquetes: `uv`.
- Estructura: Cookiecutter Data Science (directorios `data/raw`, `data/interim`, `data/processed`, `docs`).
- Computo Lógico: Pandas (vectorizado) y DuckDB (para consultas SQL sobre Parquet).
- NLP: spaCy (`es_core_news_sm`), scikit-learn (TF-IDF/LDA ligero para tópicos) o modelos locales ligeros en Ollama si se requieren embeddings semánticos.
- Tono: Académico, objetivo e investigativo. Se deben justificar las decisiones metodológicas de PLN.

---

## Fase 0: Inicialización y Documentación (Continuo)
**Objetivo:** Mantener un registro vivo del proyecto.
**Pasos:**
1. El agente creará o actualizará el archivo `docs/README.md` detallando el objetivo del proyecto (Análisis de Brecha de Visibilidad y Tópicos por Programa Académico), la metodología y el progreso actual. Este paso se repetirá tras completar cada fase.

---

## Fase 1: Pre-procesamiento y Estandarización de Entidades (Activar Skill 1)
**Objetivo:** Limpiar el DataFrame crudo, aislar y clasificar los programas académicos.
**Pasos:**
1. El usuario proporcionará el script o el DataFrame inicial. (Recomendación: para este nuevo enfoque, es eficiente descargar el corpus completo si es manejable, o utilizar la muestra representativa ya extraída para establecer el pipeline).
2. El agente asumirá el **Skill 1 (Agente de Limpieza)**.
3. Redactará el código Python optimizado (`pandas` + `regex`/`spaCy`) para extraer, clasificar (Pregrado/Posgrado) y estandarizar los programas.
4. **ALTO:** Imprimirá el Top 20 de programas encontrados (y el Bottom 5) y esperará validación antes de guardar en `data/interim`. Actualizará el README.

---

## Fase 2: Cuantificación de Cobertura y Brecha Mediática (Activar Skill 2)
**Objetivo:** Medir la disparidad en la representación de los programas a lo largo del tiempo.
**Pasos:**
1. Validada la Fase 1, el agente asumirá el **Skill 2 (Analista de Visibilidad)**.
2. Escribirá código (usando `DuckDB` o `pandas`) para calcular la frecuencia de cada programa, el porcentaje de cobertura institucional y la evolución temporal.
3. Identificará los programas dominantes y los "olvidados" (cuartil inferior).
4. **ALTO:** Presentará una tabla resumen con las métricas de cobertura. Esperará confirmación para proceder a la Fase 3. Actualizará el README.

---

## Fase 3: Modelado de Tópicos por Programa (Skill 2 Continuación)
**Objetivo:** Descubrir las narrativas asociadas a los programas (¿de qué se habla cuando se menciona X programa?).
**Pasos:**
1. El agente propondrá un script para extraer tópicos. Para priorizar la eficiencia de tokens y recursos de GPU (4GB VRAM):
   - Sugerirá usar `scikit-learn` con TF-IDF y NMF o LDA para un modelado de tópicos clásico y ultrarrápido, agrupando los textos por programa o nivel (Pregrado vs Posgrado).
   - Justificará académicamente esta elección frente a enfoques más pesados.
2. Tras procesar los datos, asignará un tópico principal a los programas clave.
3. **ALTO:** Mostrará los tópicos extraídos para los programas más y menos representados. Actualizará el README.

---

## Fase 4: Estructuración de la Narrativa Periodística/Académica
**Objetivo:** Proveer la estructura basada en evidencia para el artículo o reporte.
**Pasos:**
1. Con los datos validados, el agente redactará el esquema de la historia en formato Markdown, enfocado en:
   - **El Estatus Quo:** Qué programas acaparan el micrófono institucional y la brecha Pregrado vs. Posgrado.
   - **La Evolución:** Cómo ha cambiado la agenda de prioridades académicas con el tiempo.
   - **El Discurso:** Qué temas (tópicos) se utilizan para proyectar a las diferentes áreas de conocimiento.
2. Sugerirá gráficos (ej. gráficos de barras horizontales para cobertura, *streamgraphs* para evolución temporal) con código `matplotlib/seaborn`.
