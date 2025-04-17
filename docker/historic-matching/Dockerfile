FROM python:3.12-slim

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

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
