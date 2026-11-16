# Imagen para publicar Factor Solar en un servicio en la nube (por ejemplo Render).
# Etapa 1: construye el frontend (React) a archivos estáticos.
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Etapa 2: backend en Python que sirve la API y el frontend construido.
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY datos/ejemplos/ datos/ejemplos/
COPY --from=frontend /app/frontend/dist frontend/dist

# En la nube el dominio no es localhost: se aceptan los hosts indicados en FACTOR_SOLAR_HOSTS.
ENV FACTOR_SOLAR_HOSTS="*" \
    PORT=8000
WORKDIR /app/backend
# --proxy-headers: detrás del proxy HTTPS de la nube, la app ve el esquema real (https).
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
