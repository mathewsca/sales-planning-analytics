-- Um único servidor PostgreSQL, bancos isolados por responsabilidade:
--   warehouse -> dados analíticos (raw / staging / marts / ml)
--   airflow   -> metadados do orquestrador
--   mlflow    -> backend store do tracking server e do model registry
--   superset  -> metadados do BI (dashboards, usuários, papéis, RLS)
CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;

CREATE USER mlflow WITH PASSWORD 'mlflow';
CREATE DATABASE mlflow OWNER mlflow;

CREATE USER superset WITH PASSWORD 'superset';
CREATE DATABASE superset OWNER superset;

\connect warehouse
CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION analytics;
CREATE SCHEMA IF NOT EXISTS staging AUTHORIZATION analytics;
CREATE SCHEMA IF NOT EXISTS marts AUTHORIZATION analytics;
CREATE SCHEMA IF NOT EXISTS ml AUTHORIZATION analytics;

-- Usuário somente leitura para o BI (Superset): princípio do menor privilégio.
-- Lê apenas a camada semântica (marts) e as saídas de modelos (ml), nunca raw/staging.
CREATE USER bi_reader WITH PASSWORD 'bi_reader';
GRANT CONNECT ON DATABASE warehouse TO bi_reader;
GRANT USAGE ON SCHEMA marts, ml TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR USER analytics IN SCHEMA marts GRANT SELECT ON TABLES TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR USER analytics IN SCHEMA ml GRANT SELECT ON TABLES TO bi_reader;
