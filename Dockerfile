FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# libs do WeasyPrint (pango) e do pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles
USER app

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi -b 0.0.0.0:8000 -w 3"]
