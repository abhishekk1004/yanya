# Production image. Ships GDAL/GEOS so PostGIS-backed spatial features can be
# added later; local-native dev does not require these.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=main.settings \
    DEBUG=False

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev binutils libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
