# Factor Solar

Aplicación web local que calcula el **factor de corrección de ERA5** para cualquier punto del mapa:
eliges el sitio y el año, aportas los datos de un sensor de irradiancia (un CSV propio, un sensor
simulado para ese punto o un ejemplo listo) y la app corre el mismo pipeline ETL de la AE4 —extraer
ERA5 y NASA POWER, limpiar, llevar todo a hora UTC, unir y calcular— y muestra el factor con su
chequeo cruzado contra NASA POWER. Es **valor agregado, aparte de la entrega AE4**: demuestra que el
método no depende de Rionegro. No forma parte de la entrega ni de la guía.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o más nuevo (con "Add python.exe to PATH").
- Node.js 20 o más nuevo (solo para construir la interfaz la primera vez).
- Internet: la app consulta Open-Meteo (ERA5, siempre `models=era5`) y NASA POWER en vivo; las
  respuestas quedan guardadas en `datos/cache/` y no se vuelven a pedir.

## Cómo abrirla

Doble clic en `iniciar.bat`. La primera vez crea `backend\.venv`, instala las dependencias y
construye la interfaz (unos minutos); las siguientes arranca en segundos. Abre
http://localhost:8000 en el navegador. Deja abierta la ventana de comandos mientras usas la app;
para cerrarla, ciérrala o pulsa Ctrl+C.

## Cómo usarla

1. **Sitio:** busca un lugar, escribe las coordenadas o haz clic en el mapa.
2. **Año:** de 2015 a 2025 (años completos con ERA5 y NASA).
3. **Sensor:** sube tu CSV, simula uno para ese punto o usa un ejemplo.
4. **Calcular el factor.** El informe muestra el factor anual y mensual, la energía mensual, el
   día típico, el chequeo de desfase, la calidad de los datos antes y después de limpiar y la
   comparación ERA5–NASA. El botón "Descargar resultados (ZIP)" entrega las tablas.

## Formato del CSV

```
ts_utc,irr_sitio,t_modulo
2024-01-01 00:00:00,0.0,18.4
2024-01-01 00:01:00,0.0,18.3
```

- `ts_utc`: fecha y hora en **UTC**, por minuto o por hora (`AAAA-MM-DD HH:MM:SS`).
- `irr_sitio`: irradiancia en W/m². `t_modulo` (°C) es opcional.
- Separador coma o punto y coma; decimales con punto (o con coma si el separador es punto y coma).
  El año sale del archivo.
- Cobertura mínima: 5 % del año; con menos del 80 % la app avisa.
- Las tablas del ZIP usan punto decimal (para Excel, Python o R); la pantalla usa coma decimal.

Prueba rápida: `datos/prueba/sensor_rionegro_2024_CRUDO.csv.gz` es el sensor de la AE4
(descomprímelo antes de subirlo). Con el punto 6,147148; −75,377316 y el año 2024 la app da
el factor ERA5 **0,9103**, igual que el pipeline de la AE4.

## Honestidad sobre los datos

- Un sensor **simulado** se fabrica con el clima ERA5 del mismo punto y un supuesto declarado
  (ERA5 sobrestima más con nubes). Todo resultado simulado lleva el sello **SIMULADO** y sus
  supuestos; sirve para comprobar el método, no es una medición ni sirve para cotizar.
- Un CSV subido se rotula **"datos del usuario"**: la app no puede comprobar que venga de un sensor
  real. El sensor de prueba de la AE4 también es simulado, aunque la app lo trate como datos subidos.
- NASA POWER se usa solo como chequeo cruzado; el factor de cotización es el de ERA5.

## Para desarrollo

- Backend: `cd backend && python -m uvicorn app:app --port 8000`; pruebas:
  `python -m pytest -q -p no:cacheprovider tests`.
- Interfaz: `cd frontend && npm run dev` (o `npm run dev:mock`, sin backend).
- Capturas y pruebas de punta a punta: `npm run capturas` (con `QA_MODO=real` y el backend
  encendido, usa la API real).
