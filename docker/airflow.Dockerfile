# Airflow + um virtualenv isolado com as dependências do projeto (dbt, scikit-learn, LightGBM, MLflow).
# Isolar evita conflitos de versão entre o Airflow e as bibliotecas de ML; as tasks rodam com
# @task.external_python / BashOperator apontando para /opt/project-venv.
FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md /opt/project/
COPY src /opt/project/src
RUN python -m venv /opt/project-venv \
    && /opt/project-venv/bin/pip install --no-cache-dir uv==0.13.8 \
    && /opt/project-venv/bin/uv pip install --python /opt/project-venv/bin/python -e "/opt/project[dbt]" \
    && chown -R airflow: /opt/project /opt/project-venv
USER airflow
ENV PROJECT_PYTHON=/opt/project-venv/bin/python MLFLOW_DISABLE_AGENT_HINT=1
