FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend/index.html frontend/index.html
COPY frontend/static frontend/static

RUN useradd --create-home --uid 10001 saveloop
USER saveloop
WORKDIR /srv/backend
EXPOSE 8000

# --no-access-log: no IPs or URLs are written to logs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
