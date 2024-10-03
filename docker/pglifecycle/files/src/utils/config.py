from os import getenv


# General Configuration
AWS_REGION = getenv('AWS_REGION', 'eu-west-2')
ENVIRONMENT = getenv('PROJECT_ENV', 'local')
LOG_LEVEL = getenv('LOG_LEVEL', 'DEBUG')
PROJECT_NAME = getenv('PROJECT_NAME')

# PostgreSQL Configuration
POSTGRES_HOST = getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = getenv('POSTGRES_PORT', "5432")