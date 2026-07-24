FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS dependencies
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/src ./src
RUN pip install --upgrade pip && pip install .

FROM base AS runner
RUN addgroup --system civicos && adduser --system --ingroup civicos civicos
COPY --from=dependencies /usr/local /usr/local
COPY backend/src ./src
# Migration files are copied from their canonical repository boundary. The
# pre-deploy runner records each applied checksum before the API is started.
COPY database/migrations ./database/migrations
USER civicos
EXPOSE 8000
CMD ["sh", "-c", "exec fastapi run src/civicos_api/main.py --host 0.0.0.0 --port \"${PORT:-8000}\""]
