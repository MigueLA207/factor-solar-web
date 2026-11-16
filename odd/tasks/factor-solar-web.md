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
- [x] W2 — Frontend v1: mapa, flujo, progreso por fases, resultados (delegado; ruta: escritor delegado, 2+ archivos no triviales). Evidencia abajo.
- [x] W3 — QA y correcciones: Fig. 1, formato decimal, estados de error, CSV de la AE4 de punta a punta (0,9103), instantáneas fuera de git, `iniciar.bat`, README, capturas y detector (delegado; ruta: escritor delegado, 2+ archivos no triviales). Evidencia abajo.
- [ ] W4 — Revisión independiente (corrección de cálculos, honestidad "simulado", UX) y correcciones. Ronda 1 del juicio aplicada (20 hallazgos, ver abajo); falta la revisión de la ronda 2.
- [ ] W5 — Informe de la mañana. (`iniciar.bat` y README se hicieron en W3.)

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

- 16/11/2026 ~05:45 — W2 terminado (frontend). Evidencia:
  - `cd frontend && npm run build` → `tsc -b` sin errores, `vite build` ok.
  - Playwright (`frontend/qa/capturas.spec.ts`), 1440 y 390 px, modo mock y contra el backend real
    (ejemplo Rionegro 2024 + régimen bimodal): 4 de 4 pruebas pasan; capturas en `qa/capturas/`
    (`mock-*` y `real-*`: inicio, sensor, progreso, resultados, detalles, lectura al pasar el puntero).
  - Con el backend real el informe muestra factor ERA5 **0,8983**, verdadero 0,8997, sesgo 11,3 %,
    r ERA5–NASA 0,947, +7,8 %, desfase 0 h (cifras de la API, solo formateadas).
  - Detector Impeccable sobre la página viva (1440 y 390) y sobre la instantánea HTML del informe
    (`qa/instantaneas/real-resultados.html`): queda 1 hallazgo, `cramped-padding` en `mapa__lienzo`
    (el contenedor de Leaflet: teselas y controles van a ras del marco por diseño del mapa; justificado).
  - taste-skill: `copy-lint` 0 FAIL, 1 WARN (`copy-stat-strip`: selector de años y cifras del informe, que
    son el producto; justificado). `check.mjs` no aplica a una SPA (espera secciones de página de marketing;
    termina con error de estructura), así que su gate no se corrió.

- 16/11/2026 ~06:30 — W3 terminado. Evidencia (`<comando>: <resultado>`):
  - `cd backend && python -m pytest -q -p no:cacheprovider tests`: 37 passed (33 + 4 de `test_formato.py`;
    `test_cruce_ae4.py` ahora también exige "Correlación 0,947" y "+7,76 %" en la conclusión).
  - `cd frontend && npm run build`: `tsc -b` sin errores, `vite build` ok.
  - `QA_MODO=real npx playwright test -c qa/playwright.config.ts` (backend real en :8000): 5 de 5 pasan.
    - `e2e-real.spec.ts` › "el sensor de la AE4 da el factor de la AE4": punto 6,147148; −75,377316, año 2024,
      sube `datos/prueba/sensor_rionegro_2024_CRUDO.csv.gz` (descomprimido en memoria; 526 594 registros por
      minuto), régimen bimodal. La UI muestra factor ERA5 **0,9103**, "el factor sería 0,9809" (NASA),
      "+7,76 %" y "Correlación 0,947"; 4 846 horas; el informe no tiene ninguna cifra con punto decimal; los 12
      tallos de la Fig. 1 terminan en el borde de su punto. Captura `qa/capturas/real-07-csv-ae4-1440.png`
      (y `real-07-csv-ae4-hallazgo-1440.png`). ERA5/NASA vinieron por la extracción de la app (caché local de
      la app, no las respuestas de `datos/referencia/`).
    - Estados de error a 1440 y 390: `real-08-sin-servidor-*`, `real-08-sin-servidor-detenido-*`,
      `real-09-pedido-rechazado-*`, `real-10-etapa-con-error-*` (y el reintento termina el informe).
    - `capturas.spec.ts` regeneró `real-01` a `real-06` a 1440 y 390.
  - Detector Impeccable en la página viva (`detect --viewport 1440x900` y `390x844` sobre http://127.0.0.1:5175/):
    0 hallazgos. Sobre las instantáneas del informe, del CSV de la AE4 y del error: 1 hallazgo en cada una,
    `cramped-padding` en `mapa__lienzo` (Leaflet; ya justificado en W2).
  - Lanzador: `FACTOR_SOLAR_SIN_NAVEGADOR=1 cmd /c iniciar.bat` sin `backend\.venv`: creó el entorno, instaló
    `requirements.txt`, reconstruyó la interfaz (src más nuevo que dist) y arrancó uvicorn; `/api/salud` → 200,
    `/` → 200 text/html "Factor Solar". Segunda corrida: "Entorno listo / Dependencias al día / Interfaz al día"
    y arranca en segundos. Servidor detenido después.

- 16/11/2026 (noche) — W4, ronda 1 del juicio aplicada (20 hallazgos). Evidencia (`<comando>: <resultado>`):
  - `cd backend && python -m pytest -q -p no:cacheprovider tests`: 130 passed (37 de W3 + 93 nuevas/parametrizadas:
    `test_nasa_regla`, `test_robustez`, `test_confianza`, `test_transformacion` corregido). `test_cruce_ae4.py` sigue
    en verde: ERA5 **0,9103**, NASA **0,9809**, desfase NASA +6 h, 4 846 horas.
  - `cd frontend && npm run build`: `tsc -b` sin errores, `vite build` ok.
  - `QA_MODO=real npx playwright test -c qa/playwright.config.ts` (backend real en :8000, Vite en :5175): 12 de 12
    pasan: `capturas` (2), `e2e-real` (3, incluida la subida del CSV de la AE4 → **0,9103** / «el factor sería 0,9809» /
    «+7,76 %» / «Correlación 0,947») y `honestidad.spec.ts` (7, nuevas: factor > 1, simulado, datos subidos, nulos,
    año parcial + reloj corrido + unidades, anexos plegados a 390 px, contraste).
  - Capturas principales regeneradas en `qa/capturas/` (`real-01` … `real-10` a 1440 y 390; `honestidad-*` nuevas).
  - Detector Impeccable (`detect --viewport 1440x900` y `390x844`): página viva 0 hallazgos; instantáneas del informe
    simulado, del CSV de la AE4 y del error: solo `cramped-padding` en `mapa__lienzo` (Leaflet, ya justificado en W2).
    En el camino salió un `tight-leading` real en el hallazgo (el título ahora comparte fila con el sello y se partía en
    dos líneas con interlineado 1,2): corregido con interlineado 1,3–1,4.

- 16/11/2026 — W4, ronda 3 del juicio aplicada (9 puntos): Fig. 1 sin rótulo «año 0,90» y con línea anual de 3 px
  (leyenda con trazos fieles: gruesa, línea con punto, discontinua); regla sin recorte a la derecha; «del año»; error
  absoluto calculado desde los valores a 4 decimales; supuestos con coma (se redactan de nuevo al cargar un sensor
  simulado, porque los JSON de `datos/ejemplos/` traían punto); unidades en ejes (Fig. 2 «kWh/m² por mes», Fig. 3
  «W/m²», Fig. 4 «desfase en horas (respecto de ERA5)»); explicaciones de NASA plegadas en `<details>` «Ver detalle»;
  mensaje CSRF sin `localhost:8000`. `pytest`: 130 passed; `npm run build`: ok. Capturas en `qa/revision-final/`.

## Decisiones W4 (ronda 1 del juicio)
- **Regla de hora de NASA (hallazgo 4).** Se aplica a `cabecera_nasa["lon"]` (longitud de la celda que devuelve NASA).
  Medido sobre las 8 ubicaciones reales en caché (y 3 más), corrimiento que de verdad maximiza la correlación con ERA5
  contra lo que da cada regla (`desfase = 1 − offset`):
  | sitio | lon | mejor corr. | `round(lon/15)` | `int(lon/15)` (trunca) |
  |---|---|---|---|---|
  | Turín | 7,69 | +1 | +0 (falla) | +1 |
  | Tokio | 139,69 | −8 | −8 | −8 |
  | Sídney | 151,21 | −9 | −9 | −9 |
  | Hawái | −155,58 | +11 | +11 | +11 |
  | Delhi | 77,21 | −4 | −4 | −4 |
  | Santiago | −70,67 | +6 | +6 | +5 (falla) |
  | Berna | 7,44 | +1 | +1 | +1 |
  | Rionegro | −75,38 | +6 | +6 | +6 |
  | Bogotá | −74,07 | +6 | +6 | +5 (falla) |
  | Barranquilla | −74,80 | +6 | +6 | +5 (falla) |
  | Madrid | −3,70 | +1 | +1 | +1 |
  Resultado: **`round(lon/15)` acierta 10 de 11 (solo falla Turín, borde de franja); `int(lon/15)` acierta 8 de 11 y
  falla en las tres longitudes oeste cercanas a −4,7…−5 franjas** (el truncado va hacia 0). Se queda `round`
  (redondeo «medio hacia arriba», determinista) con la salvaguarda empírica ±1 h y su advertencia. Turín es el único
  caso en que la salvaguarda cambia el resultado (+1 en vez de +0); queda como prueba. Hipótesis NO verificada: NASA
  podría ajustar la longitud a su malla de 0,625° antes de redondear (7,69 y 7,44 caen ambos en la celda de 7,5° y
  ambos dan offset 0); con una sola observación de borde no se codificó. Nota: la longitud que NASA devuelve en la
  cabecera coincide con la pedida (redondeada a 4 decimales) en las 11 respuestas guardadas, así que hoy la regla da
  lo mismo con una u otra; se usa la de la cabecera porque es la que NASA dice haber usado. El corrimiento ELEGIDO
  (no el de la regla) se pasa a `calidad.limpiar_nasa` (la fila de calidad y el conteo de «luz de noche» lo usan).
- **Honestidad de la hora (hallazgo 2).** El corrimiento de NASA se elige contra ERA5 (regla y ±1 h por correlación), así
  que ERA5–NASA no es independiente y solo descarta errores > 1 h. La UI ya no dice «la alineación de la hora está
  bien»; muestra junto a la Fig. 4 la tabla de las correlaciones de los tres candidatos ANTES de elegir. Solo
  sensor–ERA5 es un chequeo independiente, y solo con datos subidos.
- **Sensor simulado (hallazgos 1 y 3).** Sello SIMULADO dentro del bloque del factor, fórmula «energía del sensor
  simulado = ERA5 × f», frase «En esta simulación ERA5 se pasa X % (porque la simulación lo supone)»; Fig. 4 sensor–ERA5
  «no informativo» (no se dibuja); el bloque del factor verdadero dice que comprueba coherencia interna; se oculta «con
  NASA el factor sería…». Con datos subidos: «energía del sensor = ERA5 × f» (nunca «energía real»).
- **Factor > 1 (13).** Todo texto del factor ramifica por el signo de `sesgo_relativo_pct` (`leerSesgo`): «se pasa /
  sobrestima» o «se queda corto / subestima»; la regla dibuja el tramo rayado a continuación de la barra de ERA5 hasta la
  del sensor cuando falta energía. Arreglado de paso: los ejes de la regla y de energía mensual/día típico no llegaban al
  máximo de los datos (barras que se salían del eje) → `marcasQueCubren`.
- **Nulos (14).** `num()`/`pct()` devuelven «—» para null/NaN; ningún `?? 0`; sin interpretación cuando falta el dato; los
  meses sin dato no se dibujan en Fig. 1/2.
- **Año parcial (16).** `cobertura`: un mes cuenta si el sensor cubre ≥ 50 % de sus horas diurnas con ERA5. Con menos de 12
  meses, el hallazgo dice «(parcial)» y nombra los meses con datos y sin datos; «factor anual» solo en años completos.
- **Reloj y unidades (17, 18).** Solo datos subidos: mejor desfase sensor–ERA5 ≠ 0 → «No confiable: posible desfase de
  hora en el CSV» junto al número. Aviso de unidades si el factor anual < 0,5 o > 1,5, o si la mediana de los máximos
  diarios del sensor < 50 W/m². Son avisos orientativos (umbrales míos, no de la guía).
- **Energía mensual de NASA (15).** Se suma solo donde NASA tiene dato y lleva sus propias horas (`nasa_n_horas`); es null
  si no hay ninguna.
- **Día típico (11).** Se elige dibujar en el centro del intervalo (H − 0,5) y no rotular el eje con un aviso: es más
  limpio y exacto (el dato de la etiqueta 7 es el promedio de 6:00–7:00 y va a las 6:30). El backend manda `hora_centro`
  (ordenado) y conserva `hora_local` (etiqueta de fin de intervalo).
- **Fechas del CSV (10).** Solo ISO `AAAA-MM-DD hh:mm[:ss]` (T o espacio; zona opcional). Las fechas con barras se rechazan
  con un mensaje que explica la ambigüedad día/mes.
- **Caché (5).** Escritura atómica (archivo temporal + `os.replace`), validación al leer (se parsea y se exige el año
  completo: 8 760/8 784 horas ERA5; NASA entre año y año + 2 días) y borrado + nueva consulta si está corrupta; una
  respuesta nueva inválida no se guarda; un candado por archivo evita descargas dobles.
- **IDs (6).** `^an-[0-9a-f]{10}$` (análisis), `^(sim|csv)-[0-9a-f]{10}$` o `ejemplo-<slug conocido>` (sensores),
  comprobados antes de tocar el disco en `leer_meta`, `cargar_sensor`, `guardar_sensor`, `estado_analisis` y
  `zip_analisis`.
- **Parámetros del simulador (7).** Modelos pydantic con rangos (a, b ∈ [0, 2]; factor_min/máx ∈ [0,1; 2] con
  min ≤ máx; σ ∈ [0; 0,5]; ventana 1–60 min; k ∈ [0; 0,1]; ruido T ∈ [0; 5]; cada defecto 0–10 000; claves
  desconocidas prohibidas; año 2015–2025; semilla 0–2³²−1; nombre ≤ 120). Errores 422 en español; cualquier excepción no
  prevista → 500 en español sin traza (la traza queda en el registro del servidor).
- **Exposición local (8).** `TrustedHostMiddleware` (localhost, 127.0.0.1); en POST/PUT/PATCH/DELETE con `Origin`, solo se
  acepta el mismo origen (esquema y host:puerto) o los orígenes de desarrollo de Vite (localhost/127.0.0.1, puertos
  51xx y 4173); sin `Origin` (curl, pruebas) pasa. Límite de subida 30 MB (el CSV de la AE4 descomprimido pesa ~16 MB);
  el manejador de subida es `def` (corre en el hilo de FastAPI, no bloquea). Las pruebas usan `base_url=http://localhost`.
- **Memoria y errores (9).** `_analisis` guarda como máximo 20 terminados (los resultados siguen en disco; uno con error
  sale de memoria al expulsarse). Si una excepción cae entre etapas, se marca como error la que estaba en curso, o la
  primera pendiente, o la última si ya estaban todas listas: la UI nunca muestra todo en verde con un error. El sondeo
  devuelve `resultado` solo cuando el análisis está listo.
- **Contraste (12).** Medido de forma estática, el detalle de cada paso ya daba 7,8:1 (`--tinta-2` sobre papel); el único
  cuadro con poco contraste era el fundido de opacidad de 260 ms (`aparecer`). Se cambió por un recorte (`clip-path`) y una
  prueba E2E mide el contraste y que no haya animación de opacidad.
- **Otros (19, 20).** «horas con sol» → «horas diurnas» en toda la UI; el selector de año dice cuál queda fijo por el sensor
  y que 2025 es el último año completo; a ≤ 560 px los anexos de calidad y fuentes arrancan plegados (`<details>`); se
  quitaron las dos sombras suaves restantes (buscador y lectura de las gráficas): quedan con el borde de 1 px. Se
  evitó el `border-left` grueso en las alertas del hallazgo (prohibido por la skill) usando borde de 1 px completo.
- **Prueba vacua (tests).** `test_chequeo_de_desfase_detecta_una_hora_corrida` aceptaba cualquier valor ≠ 0; ahora exige el
  corrimiento exacto (+1, −2, +3) y que ERA5–NASA quede en 0, y comprueba que sin corrimiento no hay avisos.
- **Pendiente / límites.** Las pruebas que usan respuestas reales de Turín, Sídney, Tokio, Hawái, etc. leen
  `datos/cache/` (no versionada): si falta, se saltan. No se probó una subida de >30 MB real (se prueba el 413 con 30 MB + 1 B).

## Decisiones W3
- **Fig. 1.** La geometría ya terminaba el tallo en el punto (medido en el DOM); lo que se leía como "tallo hasta
  abajo" era la marca del factor verdadero cruzando tallo y punto. Ahora el tallo para en el borde del punto y la
  muesca del verdadero va a la derecha del tallo, sin cruzarlo. Una prueba E2E lo vigila.
- **Cifras en frases del backend** (`backend/nucleo/formato.py`): coma decimal y espacio fino (U+202F) de miles,
  igual que la UI; coordenadas en frases separadas por ";". El JSON y los CSV del ZIP siguen con punto decimal
  (lo dice `LEEME.txt`). La diferencia ERA5–NASA se muestra con 2 decimales (+7,76 %, como la AE4).
- **Datos subidos.** `etiqueta_sensor` pasa de "MEDIDO (CSV subido)" a "DATOS DEL USUARIO (CSV subido)"; el
  informe muestra una franja en tinta "Datos del usuario": la app no puede comprobar que vengan de un sensor
  real. Matiz: el CSV de la AE4 es simulado, pero subido se trata como datos del usuario (`simulado: false`).
  El nombre del sitio ya no cae al nombre del archivo ("punto elegido en el mapa").
- **Subida de CSV**: ya no se manda el año elegido; el año lo fija el archivo (antes, con 2025 por defecto, un
  CSV de 2024 se podía rechazar). Arreglado de paso: la UI leía `avisos` y el backend manda `advertencias`.
- **Errores.** Tres casos, mismo bloque editorial (regla roja arriba, título serif, qué pasó, qué hacer,
  "Reintentar" y "Revisar los datos"), puesto antes del registro de pasos: sin servidor (además, franja en tinta
  bajo la cabecera con "Reintentar la conexión" si `/api/salud` no responde al abrir), pedido rechazado
  (`{"detail":{"mensaje":...}}`) y etapa con error (nombra la etapa). Los casos (b) y (c) se provocan en la
  prueba interceptando la API con Playwright; el (a) abortando las llamadas a `/api/`.
- **Instantáneas HTML** (`qa/instantaneas/`): fuera de git y en `.gitignore` (traían rutas locales). Siguen en
  la historia del commit 6c4855a (sin push; reescribir la historia no se hizo).
- **Sensor de prueba**: se versiona solo `datos/prueba/sensor_rionegro_2024_CRUDO.csv.gz` (2,8 MB; idéntico,
  SHA-256, a `datos/referencia/ae4_sensor_rionegro_2024_CRUDO.csv.gz`); el `.csv` sin comprimir está ignorado.
- **Lanzador**: `iniciar.bat` usa `py -3` o `python`, sello `backend\.venv
equisitos-instalados.txt` para
  reinstalar solo si cambia `requirements.txt`, reconstruye si `src`, `index.html` o `package.json` son más
  nuevos que `dist\index.html`, avisa si el puerto 8000 está ocupado, sirve en 127.0.0.1 y abre el navegador
  cuando `/api/salud` responde. `FACTOR_SOLAR_SIN_NAVEGADOR=1` es para pruebas.
- taste-skill (`design-taste-frontend`): sigue sin aplicar su gate a esta SPA (es para sitios de marketing); se
  respetaron sus reglas generales de copia y estados.

## Decisiones de diseño W2
- **Mundo fijado por Miguel** (no se tiró la ruleta de Impeccable: `seed: none (pinned)`): "editorial /
  instrumento de ingeniería; papel y tinta + uno o dos acentos con significado; reglas finas en vez de cajas;
  rejilla apretada; gráficas de informe científico, no de dashboard". Modo Impeccable: Operate (herramienta),
  construcción en código (sin comps). No se escribió `PRODUCT.md`/`DESIGN.md` en la raíz porque está fuera
  de la superficie autorizada de W2; el contexto de producto queda en este documento.
- **Paleta.** Papel `#f4f4f0`, tinta `#1d2433` (3 niveles de texto, el más claro `#5f6674` ≥ 4,5:1), reglas
  `#cfcfc7`. Color solo con significado: ámbar `#c8650c` = ERA5 / energía solar; azul tinta `#2b4ba0` = sensor
  (la medición); verde `#23896a` = NASA POWER; rojo `#b42318` = SIMULADO y errores. Las tres series pasaron el
  validador de la skill dataviz (banda de luminosidad, croma, CVD ΔE 9,2, visión normal ΔE 22). Solo tema
  claro: el uso es en clase/proyector y portátil de día.
- **Tipografía.** Source Serif 4 (óptica variable) para títulos y el número del factor; Public Sans para
  interfaz y datos, con cifras tabulares. Autoalojadas con @fontsource (la app funciona sin internet salvo
  mapa y APIs). Miles con espacio fino (`1 982`) para no confundir con la coma decimal.
- **Composición.** Encabezado con regla de 2 px; planilla en dos columnas (pasos 1–3 a la izquierda, mapa a la
  derecha, en una columna a 390 px con el mapa justo bajo el paso 1); pasos numerados porque el orden importa.
  Progreso como libro de registro de tres columnas (Extraer, Transformar, Cargar) con casillas cuadradas que
  se llenan. Informe como hoja técnica: banda SIMULADO roja con sello y supuestos visibles, hallazgo
  (número 0,8983 a 6 rem + fórmula + frase de sobrestimación), figuras numeradas "Fig. 1–4" con lectura en
  una frase, leyenda, lectura al pasar el puntero o con flechas del teclado y tabla plegada de datos.
- **Pieza propia.** La "regla de corrección": energía anual de ERA5 contra la del sensor sobre una regla
  graduada; el tramo rayado es lo que ERA5 pone de más. Se quitó la tercera barra (ERA5 × factor) porque
  anual es idéntica al sensor por construcción y la UI no debe recalcular.
- **Mapa.** OpenStreetMap en escala de grises por filtro CSS (las teselas de CARTO salieron con "API KEY REQUIRED" en la
  primera captura del 16/11/2026); retícula SVG propia en vez del pin de Leaflet; atribución visible.
- **Movimiento** (solo con significado, nada en bucle): vuelo del mapa al buscar o elegir ejemplo, pasos que
  avanzan en vivo, número del factor que se asienta 700 ms, curvas que se dibujan una vez, barras que crecen
  una vez. Todo se apaga con `prefers-reduced-motion`.
- **Lista negada por Miguel, cómo se evita:** sin degradados, brillos ni manchas; sin fondos de puntos; sin
  vidrio; sin tarjetas redondeadas con sombra (filas con reglas finas, radio 2 px); sin neón ni violeta; sin
  emoji ni destellos (iconos SVG propios, se quitó la bandera del prefijo de Leaflet); serif sobria y sans de
  gobierno, sin letras estilizadas; sin pastillas (sello rectangular, casillas cuadradas); héroe alineado a la
  izquierda con titular en tinta; sin bento (rejilla de 2 columnas de figuras de informe).
- **Contrato.** `frontend/src/api/tipos.ts` sigue la forma REAL del backend (b21cbac). El mock
  (`npm run dev:mock`) imita esa forma con cifras inventadas y la app muestra una franja "Modo demostración"
  y una nota al pie del informe. El régimen bimodal se pide antes de calcular (`regimen: "bimodal_andino"`);
  el año queda fijo al del sensor (ejemplo o CSV); el día típico se rotula "hora solar aprox.".
- **Pendiente para W3/W4:** revisión fresca del diseño (finish reviewer de Impeccable); subir un CSV real
  contra el backend (solo se probó la ruta en mock); estado de error con el backend apagado; textos del
  backend que traen punto decimal ("Correlación 0.947") conviven con la coma de la UI.

## Decisiones W1
- **Desfase NASA → UTC por sitio** (matizado en W4: la regla usa la longitud de la celda que devuelve NASA y el chequeo ERA5–NASA NO es independiente, ver «Decisiones W4»). NASA POWER horario entrega `time_standard: LST`; según su documentación la
  hora solar local sale de franjas de 15° de longitud → offset = round(lon/15) y desfase = 1 − offset
  (+1 h porque NASA etiqueta la hora por su inicio y Open-Meteo por su final). Rionegro → +6 (el valor fijo de
  la AE4). Medido contra ERA5 en 2023: Tokio −8, Delhi −4, Berna +1, Hawái +11, Sídney −9 coinciden con la
  regla; **Turín (lon 7,69) no**: la regla da +0 y la correlación es máxima con +1 (borde de franja). Por eso
  el núcleo prueba la regla y sus vecinos ±1 h contra ERA5 y usa el de mayor correlación; si difiere de la
  regla, lo informa como advertencia. El chequeo de desfase sensor vs ERA5 es independiente solo con datos
  subidos (con sensor simulado da 0 h por construcción).
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
