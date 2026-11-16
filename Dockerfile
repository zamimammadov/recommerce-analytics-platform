# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq is useful for PostgreSQL diagnostics; curl powers the container health check.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

COPY . /app

RUN --mount=type=secret,id=environment_ca,required=false \
    if [ -f /run/secrets/environment_ca ]; then \
      export PIP_CERT=/run/secrets/environment_ca; \
      export REQUESTS_CA_BUNDLE=/run/secrets/environment_ca; \
    fi \
    && python -m pip install -e . \
    && chown -R app:app /app

FROM runtime-base AS app
USER app

ENTRYPOINT ["recommerce"]
CMD ["--help"]

FROM runtime-base AS dbt
RUN --mount=type=secret,id=environment_ca,required=false \
    if [ -f /run/secrets/environment_ca ]; then \
      export PIP_CERT=/run/secrets/environment_ca; \
      export REQUESTS_CA_BUNDLE=/run/secrets/environment_ca; \
    fi \
    && python -m pip install "dbt-core==1.9.1" "dbt-postgres==1.9.0"
USER app
ENTRYPOINT ["dbt"]
CMD ["--help"]

FROM runtime-base AS dashboard
RUN --mount=type=secret,id=environment_ca,required=false \
    if [ -f /run/secrets/environment_ca ]; then \
      export PIP_CERT=/run/secrets/environment_ca; \
      export REQUESTS_CA_BUNDLE=/run/secrets/environment_ca; \
    fi \
    && python -m pip install -e ".[dashboard]"
USER app
ENTRYPOINT ["streamlit"]

FROM dbt AS dev
USER root
RUN --mount=type=secret,id=environment_ca,required=false \
    if [ -f /run/secrets/environment_ca ]; then \
      export PIP_CERT=/run/secrets/environment_ca; \
      export REQUESTS_CA_BUNDLE=/run/secrets/environment_ca; \
    fi \
    && python -m pip install -e ".[dev,dashboard]"
USER app
ENTRYPOINT []

FROM app AS runtime
