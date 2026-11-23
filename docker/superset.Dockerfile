# Apache Superset (versão fixada) + driver PostgreSQL (a imagem oficial é "lean", sem drivers).
FROM apache/superset:6.1.0

USER root
RUN . /app/.venv/bin/activate && uv pip install --no-cache "psycopg2-binary==2.9.10" "requests>=2.32"
USER superset
ENV SUPERSET_PORT=8088
