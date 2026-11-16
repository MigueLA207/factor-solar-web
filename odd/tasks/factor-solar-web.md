# Factor Solar Web — app interactiva del factor de corrección

## Objetivo
Una aplicación web local, bonita e impactante, donde una persona:
1. elige en un mapa el punto donde instalaría el sensor (o busca un lugar por nombre);
2. elige el año;
3. **sube el CSV de su sensor** o **simula uno** para ese punto (o carga un ejemplo ya simulado);
4. ve el pipeline correr por fases (Extraer → Transformar → Cargar) y obtiene el **factor de
   corrección** de ERA5 para ese sitio, con el chequeo cruzado contra NASA POWER.

## Por qué
Valor agregado, aparte del proyecto AE4 (Rionegro). Demuestra que el método no depende de
Rionegro: el mismo cálculo sirve para cualquier coordenada; lo único propio del sitio es el sensor.
**No forma parte de la entrega ni de la guía de estudio.** Lo pidió Miguel el 16/11/2026 y dejó
libertad creativa y trabajo autónomo durante la noche.

## Reglas
- Proyecto independiente en `C:\Users\maria\Documents\Universidad\factor-solar-web\`. No se toca nada
  de `Adquisicion_Integracion_Datos` (solo se LEE su pipeline para copiar y adaptar la lógica).
- Honestidad: todo resultado con sensor simulado dice **"SIMULADO"** de forma visible. Un factor
  simulado nunca se presenta como medición. Supuestos rotulados como supuestos.
- Open-Meteo SIEMPRE con `models=era5`. NASA POWER horario, comunidad RE, hora solar local → UTC.
- La UI va en español (neutro). Código, comentarios e identificadores: se aceptan en español para
  mantener coherencia con el pipeline original.
- Commits convencionales, sin atribución a IA. Sin push.

## Arquitectura
- `backend/` — FastAPI (Python 3.11). `backend/nucleo/` = copia adaptada del pipeline AE4
  (extracción, calidad, transformación, integración, KPI) parametrizada por lat/lon/año.
  Caché en disco de las respuestas de las API (`datos/cache/`).
- `frontend/` — Vite + React + TypeScript. Mapa con Leaflet (teselas libres con atribución).
  Gráficas propias en SVG o una librería liviana. Diseño guiado por la skill Impeccable
  (`.claude/skills/impeccable/SKILL.md`).
- `datos/ejemplos/` — sensores simulados de varias zonas listos para probar.
- Un solo comando para usarla: `iniciar.bat` (instala si hace falta, construye el frontend y lo
  sirve desde FastAPI en http://localhost:8000).

## Contrato de la API (v1)
- `GET  /api/salud`
- `GET  /api/buscar?q=texto` → lugares (Open-Meteo Geocoding).
- `GET  /api/ejemplos` → sensores de ejemplo (nombre, lat, lon, año, descripción).
- `POST /api/sensor/simular` `{lat, lon, anio, semilla?, parametros?}` → `{sensor_id, resumen}`.
- `POST /api/sensor/subir` (CSV multipart) → `{sensor_id, resumen, validacion}`.
  Formato: `ts_utc, irr_sitio[, t_modulo]`, por minuto u hora, UTC.
- `POST /api/analisis` `{lat, lon, anio, sensor_id}` → `{analisis_id}`.
- `GET  /api/analisis/{id}` → `{estado, etapas:[{fase, paso, titulo, estado, detalle}], resultado?}`.
- `GET  /api/analisis/{id}/descargar` → ZIP con las tablas.

## Simulación del sensor para cualquier punto (supuesto declarado)
Base = ERA5 de ESE punto interpolado a minutos (conservando el promedio horario, como en AE4).
Factor dependiente de la nubosidad local: ERA5 sobrestima más con nubes, así que el factor horario
baja cuando el índice de claridad (GHI_ERA5 / GHI extraterrestre) es bajo. Más ruido de nubes con
semilla. Así el sensor simulado "se parece al punto" porque depende de SU clima, pero sigue siendo
un supuesto y se rotula como tal. El factor verdadero queda guardado para mostrar la validación.

## Resultados
Factor anual y mensual de ERA5 (universal); fases del régimen bimodal solo si el usuario lo elige
(Andes colombianos). Chequeo cruzado ERA5 vs NASA (correlación y diferencia de energía), linaje,
calidad antes/después, chequeo de desfase, día típico, energía mensual (ERA5 sin corregir,
ERA5 × factor, sensor). Descarga de tablas.

## Tareas
- [x] W1 — Backend: núcleo adaptado + API + caché + simulador + ejemplos + tests (delegado; ruta: escritor delegado, 2+ archivos no triviales). Evidencia abajo.
- [ ] W2 — Frontend v1: mapa, flujo, progreso por fases, resultados (delegado).
- [ ] W3 — QA visual con Playwright + crítica Impeccable + iteración de diseño (delegado).
- [ ] W4 — Revisión independiente (corrección de cálculos, honestidad "simulado", UX) y correcciones.
- [ ] W5 — `iniciar.bat`, README corto, informe de la mañana.

## Progreso
- 16/11/2026 04:35 — Carpeta creada, git iniciado, Impeccable instalado (scope proyecto).
- 16/11/2026 ~05:10 — W1 terminado (backend). Evidencia:
  - `cd backend && python -m pytest -q -p no:cacheprovider tests` → 33 passed.
  - Prueba cruzada AE4 (sensor CRUDO de la AE4 + respuestas crudas ERA5/NASA de la AE4, copiadas en
    `datos/referencia/`): factor ERA5 **0,9103** (verdadero 0,9117), NASA **0,9809**, r ERA5–NASA 0,9467,
    diferencia total +7,76 %, fases 0,9493 / 0,8789 / 0,9283 / 0,8476, 4.846 horas, desfase 0 en ambos pares.
    Idéntico a `ae4/pipeline/salidas/factores.csv` (test `tests/test_cruce_ae4.py`).
  - uvicorn: `/api/salud` ok, `/api/ejemplos` 5 ejemplos, `/api/analisis` Santiago 2024 → ERA5 0,9299 vs
    verdadero 0,9312, NASA 0,9769, desfase 0/0, NASA +6 h; ZIP con 11 archivos.

## Decisiones W1
- **Desfase NASA → UTC por sitio.** NASA POWER horario entrega `time_standard: LST`; según su documentación la
  hora solar local sale de franjas de 15° de longitud → offset = round(lon/15) y desfase = 1 − offset
  (+1 h porque NASA etiqueta la hora por su inicio y Open-Meteo por su final). Rionegro → +6 (el valor fijo de
  la AE4). Medido contra ERA5 en 2023: Tokio −8, Delhi −4, Berna +1, Hawái +11, Sídney −9 coinciden con la
  regla; **Turín (lon 7,69) no**: la regla da +0 y la correlación es máxima con +1 (borde de franja). Por eso
  el núcleo prueba la regla y sus vecinos ±1 h contra ERA5 y usa el de mayor correlación; si difiere de la
  regla, lo informa como advertencia. El chequeo de desfase sensor vs ERA5 sigue siendo independiente.
- NASA se pide con un día extra a cada lado (`start=(año-1)1231`, `end=(año+1)0101`) para cubrir el año UTC
  completo en cualquier longitud; las horas fuera del año se descartan (se informan en `desfase`).
- **Simulador** (`backend/nucleo/simulador.py`, supuesto declarado): factor horario = a − b·(1 − kt),
  kt = GHI_ERA5 / GHI extraterrestre (12 muestras por hora; si G0 < 20 W/m² se usa el kt del día),
  a = 1,00, b = 0,25, recorte [0,70; 1,00]; ruido de nubes AE4 (σ 0,12, 7 min); t_modulo = aire + 0,03·G;
  defectos con las mismas cantidades de la AE4. Factores verdaderos anuales 2024 (semilla 2026): Rionegro
  0,8997, Barranquilla 0,9014, Bogotá 0,8825, Madrid 0,9130, Santiago 0,9312.
- Regla de calidad T_MIN baja de −10 °C (Rionegro) a −40 °C (cualquier sitio). Con el sensor de la AE4 eso hace
  que 4 de las 15 temperaturas imposibles inyectadas se detecten (las frías de −40 a −15 ya no son
  imposibles en general); no afecta el factor. El simulador nuevo inyecta las frías entre −60 y −45 °C.
- La "luz de noche" de NASA se mide con la elevación solar del sitio (no 19:00–05:00), válido en cualquier latitud.
- El chequeo de desfase ya no detiene el análisis: un máximo ≠ 0 se muestra como advertencia.
- Ejemplos versionados como `datos/ejemplos/*.csv.gz` (~2,8 MB cada uno); la caché de API y los
  sensores/análisis de cada instalación (`datos/cache`, `datos/sensores`, `datos/analisis`) no se versionan.
- Extra al contrato: `/api/salud` devuelve también `anio_min`, `anio_max`, `anio_por_defecto` (2025) y los
  parámetros por defecto del simulador; `/api/sensor/subir` acepta campos de formulario opcionales
  `anio`, `lat`, `lon`, `nombre`; `POST /api/analisis` acepta `regimen` ("bimodal_andino") y `nombre`.
  Errores: `{"detail": {"mensaje": "...", ...}}`.

## Notas para W2 (frontend)
- Arranque backend: `cd backend && python -m uvicorn app:app --port 8000` (CORS abierto a localhost:5173).
- Sensores de ejemplo: `sensor_id = "ejemplo-<slug>"`, año 2024; el análisis exige el mismo año del sensor.
- Simular en un punto nuevo tarda unos segundos (consulta ERA5 en vivo la primera vez); analizar ~3–5 s.
- Sondear `GET /api/analisis/{id}` cada ~500 ms; `estado` = en_curso | listo | error; el error va en
  `error` y en la etapa con `estado: "error"`.
- Mostrar SIEMPRE `etiqueta_sensor` ("SIMULADO") y `supuestos` cuando `simulado` es true.
