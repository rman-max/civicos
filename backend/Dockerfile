FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS dependencies
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

FROM base AS runner
RUN addgroup --system civicos && adduser --system --ingroup civicos civicos
COPY --from=dependencies /usr/local /usr/local
COPY src ./src
USER civicos
EXPOSE 8000
CMD ["fastapi", "run", "src/civicos_api/main.py", "--host", "0.0.0.0", "--port", "8000"]
