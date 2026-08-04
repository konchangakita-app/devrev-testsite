FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade "pip>=25" "wheel>=0.45" \
    && pip install --no-cache-dir -r requirements.txt

COPY helpsite ./helpsite
COPY templates ./templates
COPY static ./static
COPY init_db.py .
COPY gunicorn.conf.py .
COPY docker-entrypoint.sh .
COPY scripts ./scripts

RUN mkdir -p instance \
    && chmod +x docker-entrypoint.sh

EXPOSE 5020

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5020/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
