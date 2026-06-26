FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

RUN mkdir -p /data app/static/uploads logs

EXPOSE 8000

CMD ["sh", "-c", "python setup_db.py && gunicorn --workers ${GUNICORN_WORKERS:-1} --worker-class gevent --timeout ${GUNICORN_TIMEOUT:-120} --bind 0.0.0.0:8000 wsgi:app"]
