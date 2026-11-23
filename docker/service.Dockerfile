# Imagem multi-stage para os serviços Python (API).
#   docker build -f docker/service.Dockerfile --build-arg EXTRAS=api .
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ARG EXTRAS=api
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.13.8
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv venv /opt/venv && uv pip install --python /opt/venv/bin/python ".[${EXTRAS}]"

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /srv
COPY --chown=app api ./api

USER app
