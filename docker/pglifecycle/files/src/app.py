import json
import subprocess
from utils.aws import download_s3_dir, get_latest_object_dir
from utils.db import DatabaseUtils
from utils.db import (
    build_conn_opts,
    create_database_sql,
    create_extension_sql,
    create_role_sql,
    create_schema_sql,
    create_server_sql,
    create_user_sql,
    create_user_mapping_sql,
    grant_privileges,
    log_and_execute,
    process_entities,
    remove_datadog_monitoring,
    setup_datadog_monitoring,
)
from utils.logger import log


def destroy(conn_opts: dict, event):
    log.info(f"""DATABASE DESTROY
    Target Database: {event["targetDatabase"]}
    Role(s) to be Destroyed: {", ".join(event["roles"])}""")
    try:
        with DatabaseUtils(**conn_opts) as con:
            database_name = event["targetDatabase"]
            log_and_execute(
                con,
                f"DROP DATABASE IF EXISTS {database_name} WITH (FORCE);",
                f"Database {database_name} dropped successfully",
                f"Error dropping database {database_name}",
            )

            for role in event["roles"]:
                log_and_execute(
                    con,
                    f"DROP ROLE IF EXISTS {role};",
                    f"Role {role} dropped successfully",
                    f"Error dropping role {role}",
                )

            remove_datadog_monitoring(con)
    except Error as e:  # noqa: F821 - BODS-7131
        log.error(f"An error occurred: {e}")
        return False

    log.info("All actions were completed successfully. Exiting")
    return True


def initialise(conn_opts: dict, event):
    log.info(f"""DATABASE INITIALISATION
    Target Database(s): {", ".join(database["name"] for database in event["databases"])}
    Role(s) to be Created: {", ".join(role["name"] for role in event["roles"])}""")

    monitoring_opts = (
        event["datadogMonitoring"]
        if "datadogMonitoring" in event
        else json.loads('{"enabled": false}')
    )

    try:
        with DatabaseUtils(**conn_opts) as con:
            existing_databases = [
                row[0] for row in con.execute_sql("SELECT datname from pg_database;", 2)
            ]
            existing_roles = [
                row[0] for row in con.execute_sql("SELECT rolname FROM pg_roles;", 2)
            ]

            process_entities(
                con,
                event["databases"],
                create_database_sql,
                "database",
                existing_databases,
            )
            process_entities(
                con, event["roles"], create_role_sql, "role", existing_roles
            )
            for role in event["roles"]:
                process_entities(
                    con, role["users"], create_user_sql, "user", existing_roles
                )

            if monitoring_opts["enabled"]:
                database_name = con.execute_sql(
                    "SELECT current_database();",
                    1,
                )
                existing_schemas = [
                    row[0]
                    for row in con.execute_sql("SELECT nspname FROM pg_namespace", 2)
                ]
                setup_datadog_monitoring(
                    con,
                    database_name,
                    existing_roles,
                    existing_schemas,
                    monitoring_opts,
                    create_role=True,
                )

    except Exception as e:
        log.error(f"An error occurred: {e}")
        return False

    ## Perform actions against specific database(s)
    for database in event["databases"]:
        database_name = database["name"]
        conn_opts.update({"dbname": database_name})
        try:
            with DatabaseUtils(**conn_opts) as con:
                existing_servers = [
                    row[0]
                    for row in con.execute_sql(
                        "SELECT srvname from pg_foreign_server;", 2
                    )
                ]

                log_and_execute(
                    con,
                    "REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC;",
                    "Revoked ALL privileges on public schema",
                )
                process_entities(con, database["schemas"], create_schema_sql, "schema")
                process_entities(
                    con, database["extensions"], create_extension_sql, "extension"
                )
                process_entities(
                    con,
                    database["servers"],
                    create_server_sql,
                    "server",
                    existing_servers,
                )
                for server in database["servers"]:
                    existing_user_mappings = [
                        row[0]
                        for row in con.execute_sql(
                            f"SELECT usename from pg_user_mappings WHERE srvname = '{server['name']}';",
                            2,
                        )
                    ]
                    user_mappings = [
                        dict(item, **{"serverName": server["name"]})
                        for item in server["userMappings"]
                    ]
                    process_entities(
                        con,
                        user_mappings,
                        create_user_mapping_sql,
                        "user mapping",
                        existing_user_mappings,
                    )

                for role in event["roles"]:
                    grant_privileges(
                        con,
                        role["name"],
                        database_name,
                        role["kind"],
                        database["schemas"],
                        role.get("schemas", None),
                    )

                if monitoring_opts["enabled"]:
                    existing_schemas = [
                        row[0]
                        for row in con.execute_sql(
                            "SELECT nspname FROM pg_namespace", 2
                        )
                    ]
                    setup_datadog_monitoring(
                        con,
                        database_name,
                        None,
                        existing_schemas,
                        monitoring_opts,
                        create_role=False,
                    )

        except Exception as e:
            log.error(f"An error occurred: {e}")
            return False

    log.info("All actions were completed successfully. Exiting")
    return True


def run_migrations(conn_opts: dict, event):
    def run_liquibase_command(liquibase_properties_path: str, *args):
        command = ["liquibase", "--defaultsFile", liquibase_properties_path] + list(
            args
        )
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(
                f'Liquibase command "{" ".join(command)}" failed: {result.stderr}'
            )
            raise Exception(
                f'Liquibase command "{" ".join(command)}" failed: {result.stderr}'
            )
        log.info(f'Liquibase command "{" ".join(command)}" succeeded: {result.stdout}')

    bucket_name = event["databaseMigrations"]["bucketName"]
    bucket_prefix = event["databaseMigrations"]["bucketPrefix"]
    release_version = event["databaseMigrations"]["releaseVersion"]
    remote_path = ""
    target_database = event["targetDatabase"]
    try:
        if release_version == "latest":
            log.info(f'Determining latest version from S3 bucket "{bucket_name}"')
            latest_version = get_latest_object_dir(bucket_name, bucket_prefix)
            if latest_version:
                log.info(f"Latest version determined to be: {latest_version}")
                release_version = latest_version
            else:
                raise Exception(
                    f'No versioned objects found in the S3 bucket "{bucket_name}"'
                )
        remote_path = f"{bucket_prefix}/{release_version}/liquibase"
        local_path = f'/tmp/{remote_path.split("/")[-1]}'

        log.info(f"""DATABASE MIGRATIONS
        Source Bucket: {bucket_name}
        Source Remote Path: {remote_path}
        Release Version: {release_version}
        Target Database: {target_database}""")
        download_s3_dir(bucket_name, remote_path, local_path)

        liquibase_properties_path = f"{local_path}/liquibase.properties"
        with open(liquibase_properties_path, "w") as file:
            file.write(f"""
changeLogFile=db.changelog.xml
liquibase.command.url=jdbc:postgresql://{conn_opts['host']}:{conn_opts['port']}/{target_database}
liquibase.command.username: {conn_opts['user']}
liquibase.command.password: {conn_opts['password']}
logLevel: INFO""")

        log.info(
            f"Executing Liquibase commands for release version {release_version} against target database {target_database}"
        )
        run_liquibase_command(
            liquibase_properties_path, "--search-path", local_path, "validate"
        )
        run_liquibase_command(
            liquibase_properties_path,
            "--search-path",
            local_path,
            "status",
            "--verbose",
        )
        run_liquibase_command(
            liquibase_properties_path, "--search-path", local_path, "update"
        )
        run_liquibase_command(
            liquibase_properties_path,
            "--search-path",
            local_path,
            "history",
        )

        log.info("All files successfully processed. Exiting")

    except Exception as e:
        log.error(f"An error occurred: {e}")
        return False
    except Error as e:  # noqa: F821 - BODS-7131
        log.error(f"An error occurred: {e}")
        return False
    finally:
        subprocess.run(["rm", "-rf", local_path])

    log.info("All actions were completed successfully. Exiting")
    return True


def lambda_handler(event, context):
    try:
        pg_conn_opts = build_conn_opts(event)
        event_type = event["type"]
        if event_type == "destroy":
            success = destroy(pg_conn_opts, event)
        elif event_type == "initialise":
            success = initialise(pg_conn_opts, event)
        elif event_type == "run_migrations":
            success = run_migrations(pg_conn_opts, event)
        else:
            log.error("Invalid event type has been specified. Exiting")
            success = False

        if success:
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "[SUCCESS] All actions were completed successfully. Exiting"
                    }
                ),
            }
        else:
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "message": "[FAILURE] An error occurred when executing the specified task. Exiting"
                    }
                ),
            }
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": f"[FAILURE] An unexpected error occurred: {e}. Exiting"}
            ),
        }
