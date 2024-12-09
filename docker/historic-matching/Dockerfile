FROM python:3.12-slim

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# TODO: pull most of this from the environment in an entry point script. Anything else can go in a task definition
ENV POSTGRES_DB="abods"
ENV POSTGRES_HOST="abods-sandbox-rds-proxy.proxy-cloy20wwg36k.eu-west-2.rds.amazonaws.com"
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER="abods_proxy_rw"
ENV POWERTOOLS_SERVICE_NAME="sirivm_otp_matching_function"
ENV PROJECT_ENV="sandbox"
ENV PROJECT_NAME="abods"
ENV AWS_DEFAULT_REGION="eu-west-2"

COPY requirements.txt .
RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2 \
    && python -m pip install -r requirements.txt

HEALTHCHECK NONE
# checkov:skip=CKV_DOCKER_8:root user is fine for now
USER root

WORKDIR /app
COPY files /app


CMD ["python", "-m", "sirivm_otp_matching_function.historic_matching"]
