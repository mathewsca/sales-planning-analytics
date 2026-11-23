FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1 \
    MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false
RUN pip install --no-cache-dir "mlflow==3.18.0" "psycopg[binary]==3.3.9" \
    && useradd --create-home --uid 1000 mlflow \
    && mkdir -p /mlartifacts && chown mlflow /mlartifacts
USER mlflow
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"
