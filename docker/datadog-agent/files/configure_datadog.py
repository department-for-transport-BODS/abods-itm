#!/usr/bin/env python3
from os import getenv
from yaml import load, dump, Loader

# Load the existing configuration file
with open("/etc/datadog-agent/conf.d/postgres.d/conf.yaml.example", "r") as file:
    conf = load(file, Loader=Loader)

# Update the configuration with environment variables
conf["instances"][0]["host"] = getenv("DB_ENDPOINT")
conf["instances"][0]["dbname"] = getenv("PROJECT_NAME")
conf["instances"][0]["dbm"] = True
conf["instances"][0]["password"] = getenv("PG_DD_PASSWORD")
conf["instances"][0]["username"] = getenv("PG_DD_USERNAME")
conf["instances"][0]["tags"] = [
    f"Environment:{getenv('ENVIRONMENT')}",
    f"ProjectName:{getenv('PROJECT_NAME')}"
]

# Write the updated configuration back to the file
with open("/etc/datadog-agent/conf.d/postgres.d/conf.yaml", "w") as file:
    file.write(dump(conf))