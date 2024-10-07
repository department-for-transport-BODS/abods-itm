# PostgreSQL Mutate Containerised Application Service

## Description

This service is built currently with a view to it being run as a Lambda function within AWS. It allows for numerous functions to be run against any target database, with examples of expected JSON payloads detailed within `./files/tests`. The functions that are available for execution are:

- initialisation (of schema and roles)
- destruction (of schema and roles)
- database migration execution (using a defined location in S3 where `.sql` file are stored, using liquibase changelogs to execute each in turn)

## Usage

In order to build the service, use standard Docker syntax as below:

```bash
#!/usr/bin/env bash

docker build --platform linux/x86_64 -t pglifecycle .
```

When testing the service locally, we can mock Lambda and make it available to accept requests. It is necessary to export variables for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` in order to interact with S3 on the backend (specifically for the _run-migrations_ action). It will also be necessary to specify various connection parameters for access to any backend database, be that local or remote; the example below is using a SSH tunnel connection to a private Amazon RDS instance, however your requirements may differ.

```bash
#!/usr/bin/env bash

docker run --platform linux/x86_64 --name pglifecycle --network=lambda-local \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
    -e AWS_DEFAULT_REGION=eu-west-2 \
    -e LOG_LEVEL=DEBUG \
    -e POSTGRES_HOST='host.docker.internal' -e POSTGRES_PORT=15432 \
    -e POSTGRES_USER=$POSTGRES_USER \
    -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
    -p 9000:8080 --add-host 'host.docker.internal:host-gateway' docker.io/library/pglifecycle app.lambda_handler
```

An example command to trigger the Lambda function running locally, whilst passing in an `event` is demonstrated below. This uses the [initialise event](./files/tests/event_initialise.json) JSON payload.

```bash
#!/usr/bin/env bash

curl http://localhost:9000/2015-03-31/functions/function/invocations -d @event_initialise.json | jq
```
