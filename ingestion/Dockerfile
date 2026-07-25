FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system civicos && adduser --system --ingroup civicos civicos

COPY ingestion/pyproject.toml ./
COPY ingestion/src ./src
COPY database/seeds /app/database/seeds
RUN pip install --no-cache-dir .

USER civicos

CMD ["python", "-m", "civicos_ingestion.worker"]
