# Stage 1: build the React app.
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# Stage 2: Django serves the API and the built app (WhiteNoise) from one process.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# WhiteNoise serves the app's files as they are, so compress them once here.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && python -m whitenoise.compress /app/frontend/dist \
    && useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
# One worker, so the in-memory cache and the rate limits are shared by every request on a replica.
# The work is mostly waiting on TomTom and Open-Meteo, which threads handle well.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "120", "--access-logfile", "-"]
