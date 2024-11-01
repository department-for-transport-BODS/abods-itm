#!/usr/bin/env python3
from os import getenv
from yaml import load, dump, Loader

# Load the existing configuration file
with open("/etc/datadog-agent/conf.d/postgres.d/conf.yaml.example", "r") as file:
    conf = load(file, Loader=Loader)

# Load the custom queries configuration file
with open("/tmp/custom_queries.yaml", "r") as file:
    custom_queries_config = load(file, Loader=Loader)

# Update the configuration with environment variables
conf["instances"][0]["host"] = getenv("DB_ENDPOINT")
conf["instances"][0]["dbname"] = getenv("PROJECT_NAME")
conf["instances"][0]["dbm"] = True
conf["instances"][0]["password"] = getenv("PG_DD_PASSWORD")
conf["instances"][0]["username"] = getenv("PG_DD_USERNAME")
conf["instances"][0]["tags"] = [
    f"Environment:{getenv('ENVIRONMENT')}",
    f"ProjectName:{getenv('PROJECT_NAME')}",
]

# Replace the custom_queries section with dynamic entries
conf["instances"][0]["custom_queries"] = custom_queries_config["custom_queries"]

# Update tags with environment variables in each custom query
for query in conf["instances"][0]["custom_queries"]:
    if "tags" in query:
        query["tags"].extend(
            [
                f"Environment:{getenv('ENVIRONMENT')}",
                f"ProjectName:postgresql:{getenv('PROJECT_NAME')}",
            ]
        )
    else:
        query["tags"] = [
            f"Environment:{getenv('ENVIRONMENT')}",
            f"ProjectName:postgresql:{getenv('PROJECT_NAME')}",
        ]

# Write the updated configuration back to the file
with open("/etc/datadog-agent/conf.d/postgres.d/conf.yaml", "w") as file:
    file.write(dump(conf))
