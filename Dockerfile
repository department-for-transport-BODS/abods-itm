# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.12-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV POSTGRES_DB="abods"
ENV POSTGRES_HOST="abods-sandbox-rds-proxy.proxy-cloy20wwg36k.eu-west-2.rds.amazonaws.com"
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER="abods_proxy_rw"
ENV POWERTOOLS_SERVICE_NAME="sirivm_otp_matching_function"
ENV PROJECT_ENV="sandbox"
ENV PROJECT_NAME="abods"

# Install pip requirements
COPY requirements.txt .
RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2 \
    && python -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "-m", "ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.historic_matching", "2024-11-21"]
