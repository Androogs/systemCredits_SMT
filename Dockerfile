# Imagen del backend FastAPI (motor de decisión integrado).
# Construir desde la raíz del repo:
#   docker build -t creditos-api .
# Ejecutar (con DATABASE_URL y demás .env):
#   docker run --env-file .env -p 8000:8000 creditos-api
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primero para aprovechar la caché de capas.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY alembic/ alembic/
COPY alembic.ini .

# Usuario no-root; uploads/ es el storage local de evidencias del MVP.
# La app escribe parametros.json en /app al primer arranque: chown completo.
RUN useradd --create-home --uid 1001 app \
    && mkdir -p uploads/evidencias \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Aplica migraciones pendientes y arranca la API.
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
