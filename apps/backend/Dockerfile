FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dev
RUN pip install --no-cache-dir \
    alembic \
    "bcrypt<5" \
    bleach \
    chromadb \
    fastapi \
    httpx \
    langchain-chroma \
    langchain-openai \
    passlib[bcrypt] \
    psycopg[binary] \
    python-jose[cryptography] \
    slowapi \
    sqlalchemy \
    stripe \
    structlog \
    uvicorn[standard]
COPY src/backend-generic/ /app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
RUN pip install --no-cache-dir \
    alembic \
    "bcrypt<5" \
    bleach \
    chromadb \
    fastapi \
    httpx \
    langchain-chroma \
    langchain-openai \
    passlib[bcrypt] \
    psycopg[binary] \
    python-jose[cryptography] \
    slowapi \
    sqlalchemy \
    stripe \
    structlog \
    uvicorn[standard]
COPY src/backend-generic/ /app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
