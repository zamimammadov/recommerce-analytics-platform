# syntax=docker/dockerfile:1.7
FROM apache/airflow:2.10.4-python3.11

# Airflow 2.10 uses SQLAlchemy 1.4. The pipeline uses SQLAlchemy 2, so its
# dependencies belong in a separate environment rather than Airflow's core.
USER root
RUN python -m venv /opt/recommerce-venv \
    && mkdir -p /opt/recommerce-package \
    && chown -R airflow:0 /opt/recommerce-venv /opt/recommerce-package

COPY --chown=airflow:0 pyproject.toml README.md LICENSE /opt/recommerce-package/
COPY --chown=airflow:0 src /opt/recommerce-package/src
COPY --chown=airflow:0 sql /opt/recommerce-package/sql

USER airflow
RUN --mount=type=secret,id=environment_ca,required=false \
    if [ -f /run/secrets/environment_ca ]; then \
      export PIP_CERT=/run/secrets/environment_ca; \
      export REQUESTS_CA_BUNDLE=/run/secrets/environment_ca; \
    fi \
    && PIP_USER=false /opt/recommerce-venv/bin/python -m pip install --no-cache-dir \
         /opt/recommerce-package "dbt-core==1.9.1" "dbt-postgres==1.9.0"
