import psycopg
import re
from .logger import log
from os import getenv
from psycopg import Error
from utils.aws import get_secret, generate_rds_iam_auth_token
from utils.config import ENVIRONMENT, POSTGRES_HOST, POSTGRES_PORT
from utils.logger import log  # noqa: F811 - BODS-7131


def build_conn_opts(ev):
    """
    Builds the connection options dictionary for connecting to PostgreSQL.

    Parameters:
    - event (dict): The event containing connection details and environment.

    Returns:
    - dict: The connection options for PostgreSQL.
    - None: If an error occurs while generating the IAM token.
    """
    log.debug("Setting default options for PostgreSQL connection")
    conn_opts = {"host": POSTGRES_HOST, "port": POSTGRES_PORT, "dbname": "postgres"}
    log.debug(f"Default options for PostgreSQL connection: {conn_opts}")

    if ENVIRONMENT == "local":
        conn_opts.update(
            {
                "user": getenv("POSTGRES_USER"),
                "password": getenv("POSTGRES_PASSWORD"),
                "gssencmode": "disable",
            }
        )
    else:
        log.debug(
            f"Generating IAM authentication token for login against {POSTGRES_HOST}"
        )
        username = ev["authUser"]
        token = generate_rds_iam_auth_token(POSTGRES_HOST, POSTGRES_PORT, username)
        if not token:
            log.error("Failed to generate IAM token. Exiting.")
            return None
        conn_opts.update({"user": username, "password": token, "sslmode": "require"})

    log.debug(f"Final PostgreSQL connection options: {conn_opts}")
    return conn_opts


def create_database_sql(database):
    database_name = database["name"]
    sql = f"CREATE DATABASE {database_name} WITH ENCODING UTF8;"
    return sql, f"Database {database_name} created successfully"


def create_extension_sql(extension):
    if ":" in extension:
        extension, schema = extension.split(":", 1)
        sql = f"CREATE EXTENSION IF NOT EXISTS {extension} WITH SCHEMA {schema};"
        return sql, f"Extension {extension} with schema {schema} created successfully"
    elif "+" in extension:
        extension = extension.split("+", 1)[0]
        sql = f"CREATE EXTENSION IF NOT EXISTS {extension} CASCADE;"
        return sql, f"Extension {extension} with cascade created successfully"
    else:
        sql = f"CREATE EXTENSION IF NOT EXISTS {extension};"
        return sql, f"Extension {extension} created successfully"


def create_monitoring_function_sql(schema):
    sql = f"""CREATE OR REPLACE FUNCTION {schema}.explain_statement(
      l_query TEXT,
      OUT explain JSON
    )
    RETURNS SETOF JSON AS
    $$
    DECLARE
    curs REFCURSOR;
    plan JSON;

    BEGIN
      OPEN curs FOR EXECUTE pg_catalog.concat('EXPLAIN (FORMAT JSON) ', l_query);
      FETCH curs INTO plan;
      CLOSE curs;
      RETURN QUERY SELECT plan;
    END;
    $$
    LANGUAGE 'plpgsql'
    RETURNS NULL ON NULL INPUT
    SECURITY DEFINER;"""
    return sql, "Function for DataDog monitoring created successfully"


def create_role_sql(role):
    role_name = role["name"]
    sql = f"""CREATE ROLE {role_name} WITH NOSUPERUSER NOCREATEDB NOCREATEROLE
    INHERIT NOLOGIN NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT -1;"""
    return sql, f"Role {role_name} created successfully"


def create_schema_sql(schema):
    sql = f"CREATE SCHEMA IF NOT EXISTS {schema};"
    return sql, f"Schema {schema} created successfully"


def create_server_sql(server):
    server_name = server["name"]
    host = server["options"]["host"]
    port = server["options"]["port"]
    dbname = server["options"]["dbname"]
    sql = f"""CREATE SERVER {server_name}
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '{host}', port '{port}', dbname '{dbname}');"""
    return sql, f"Server {server_name} created successfully"


def create_user_mapping_sql(user_mapping):
    user_name = user_mapping["name"]
    server_name = user_mapping["serverName"]
    credentials_arn = user_mapping["credentialsArn"]
    user_credentials = (
        get_secret(credentials_arn)
        if ENVIRONMENT != "local"
        else {"username": "local", "password": "local"}
    )
    sql = f"""CREATE USER MAPPING
    FOR {user_name}
    SERVER {server_name} 
    OPTIONS (user '{user_credentials["username"]}', password '{user_credentials["password"]}');
    GRANT USAGE ON FOREIGN SERVER {server_name} TO {user_name}"""
    return (
        sql,
        f"User Mapping {user_name} for server {server_name} created successfully",
    )


def create_user_sql(user):
    user_name = user["name"]
    role_name = (
        user["roleName"] if "roleName" in user else re.sub(r"_[^_]+_", "_", user_name)
    )
    auth_type = user["authType"]
    if auth_type == "scram":
        user_password = (
            get_secret(user["credentialsArn"])["password"]
            if ENVIRONMENT != "local"
            else "local"
        )
        sql = f"""CREATE USER {user_name} WITH NOSUPERUSER NOCREATEDB NOCREATEROLE
        INHERIT LOGIN NOREPLICATION NOBYPASSRLS
        CONNECTION LIMIT -1
        PASSWORD '{user_password}';
        GRANT {role_name} TO {user_name};"""
        success_msg = f"User {user_name} created with SCRAM authentication and granted the ROLE {role_name}"
    elif auth_type == "iam":
        sql = f"""CREATE USER {user_name} WITH NOSUPERUSER NOCREATEDB NOCREATEROLE
        INHERIT LOGIN NOREPLICATION NOBYPASSRLS
        CONNECTION LIMIT -1;
        GRANT rds_iam TO {user_name};
        GRANT {role_name} TO {user_name};"""
        success_msg = f"User {user_name} created with IAM authentication and granted the ROLES rds_iam, {role_name}"
    else:
        sql = f"""CREATE USER {user_name} WITH NOSUPERUSER NOCREATEDB NOCREATEROLE
        INHERIT LOGIN NOREPLICATION NOBYPASSRLS
        CONNECTION LIMIT -1;
        GRANT {role_name} TO {user_name};"""
        success_msg = f"User {user_name} created and granted the ROLE {role_name}"
    return sql, success_msg


def grant_privileges(con, role_name, database_name, role_kind, schemas, role_schemas):
    if role_schemas is None:
        role_schemas = []

    if role_kind == "ro":
        log_and_execute(
            con,
            f"GRANT CONNECT ON DATABASE {database_name} TO {role_name}",
            f"Granted CONNECT on {database_name} to {role_name}",
        )
        for schema in schemas + role_schemas:
            log_and_execute(
                con,
                f"GRANT USAGE ON SCHEMA {schema} TO {role_name}",
                f"Granted USAGE on schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {role_name}",
                f"Granted SELECT on all tables in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO {role_name}",
                f"Defaulted grant for SELECT on all tables in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role_name}",
                f"Granted SELECT on all sequences in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON SEQUENCES TO {role_name}",
                f"Defaulted grant for SELECT on all sequences in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"REVOKE CREATE ON SCHEMA {schema} FROM {role_name};",
                f"Revoked CREATE on schema {schema} from {role_name}",
            )

    elif role_kind == "rw":
        log_and_execute(
            con,
            f"GRANT ALL PRIVILEGES ON DATABASE {database_name} TO {role_name}",
            f"Granted ALL privileges on {database_name} to {role_name}",
        )
        for schema in schemas + role_schemas:
            log_and_execute(
                con,
                f"GRANT ALL ON SCHEMA {schema} TO {role_name}",
                f"Granted ALL on schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} TO {role_name}",
                f"Granted ALL privileges on all tables in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {role_name}",
                f"Defaulted grant for ALL on all tables in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {schema} TO {role_name}",
                f"Granted ALL privileges on all functions in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON FUNCTIONS TO {role_name}",
                f"Defaulted grant for ALL on all functions in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} TO {role_name}",
                f"Granted ALL privileges on all sequences in schema {schema} to {role_name}",
            )
            log_and_execute(
                con,
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {role_name}",
                f"Defaulted grant for ALL on all sequences in schema {schema} to {role_name}",
            )

    elif role_kind == "monitoring":
        for schema in schemas + role_schemas:
            log_and_execute(
                con,
                f"GRANT USAGE ON SCHEMA {schema} TO {role_name}",
                f"Granted USAGE on schema {schema} to {role_name}",
            )
            if schema == "cron":
                existing_tables = [
                    row[0]
                    for row in con.execute_sql(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'cron';",
                        2,
                    )
                ]
                for table in existing_tables:
                    log_and_execute(
                        con,
                        f"GRANT SELECT ON cron.{table} TO {role_name};",
                        f"Granted SELECT on table {table} in schema cron to {role_name}",
                    )
                    log_and_execute(
                        con,
                        f"CREATE POLICY {role_name}_select_policy ON cron.{table} FOR SELECT USING (current_user = '{role_name}');",
                        f"Created RLS policy for SELECT on table {table} in schema cron",
                    )
                    log_and_execute(
                        con,
                        f"ALTER TABLE cron.{table} ENABLE ROW LEVEL SECURITY;",
                        f"Enabled RLS on table {table} in schema cron",
                    )


def remove_datadog_monitoring(con):
    log.info("Removing DataDog monitoring setup...")

    log_and_execute(
        con,
        "DROP EXTENSION IF EXISTS pg_stat_statements;",
        "pg_stat_statements extension dropped successfully",
        "Error dropping pg_stat_statements EXTENSION",
    )
    log_and_execute(
        con,
        "DROP SCHEMA IF EXISTS datadog CASCADE;",
        "Successfully dropped datadog schema",
        "Error dropping datadog schema",
    )
    log_and_execute(
        con,
        "REVOKE pg_monitor FROM datadog;",
        "Successfully revoked ROLE pg_monitor from user datadog",
        "Error revoking pg_monitor ROLE",
    )
    log_and_execute(
        con,
        "REVOKE USAGE ON SCHEMA public FROM datadog;",
        "Successfully revoked USAGE on schema public from user datadog",
        "Error revoking USAGE on schema public",
    )
    log_and_execute(
        con,
        "DROP ROLE IF EXISTS datadog;",
        "Datadog USER dropped successfully",
        "Error dropping datadog USER",
    )


def setup_datadog_monitoring(
    con,
    db,
    existing_roles,
    existing_schemas,
    opts,
    create_role,
):
    log.info(f"Enabling DataDog Monitoring for {db} database")

    if create_role:
        process_entities(
            con,
            [
                dict(
                    opts,
                    **{"name": "datadog", "roleName": "pg_monitor"},
                )
            ],
            create_user_sql,
            "user",
            existing_roles,
        )

    process_entities(con, ["datadog"], create_schema_sql, "schema")

    enabled_schemas = ["datadog", "public"]
    if "cron" in existing_schemas:
        enabled_schemas.extend(["cron"])

    grant_privileges(
        con,
        "datadog",
        "postgres",
        "monitoring",
        enabled_schemas,
        None,
    )

    process_entities(
        con,
        ["pg_stat_statements:public"],
        create_extension_sql,
        "extension",
    )

    process_entities(
        con,
        ["datadog"],
        create_monitoring_function_sql,
        "monitoring function",
    )


def log_and_execute(con, sql, success_msg, error_msg=None):
    try:
        con.execute_sql(sql)
        log.info(success_msg)
    except Exception as e:
        log.error(error_msg if error_msg else str(e))


def process_entities(
    con, entities_to_create, create_sql_func, entity_type, existing_entities=None
):
    if existing_entities is None:
        existing_entities = []

    for entity in entities_to_create:
        if all(isinstance(item, dict) for item in entities_to_create):
            entity_name = entity["name"]
        elif all(isinstance(item, str) for item in entities_to_create):
            entity_name = entity
        else:
            raise TypeError("entities_to_create must be either a dict or a list")

        if entity_name not in existing_entities:
            create_sql, success_msg = create_sql_func(entity)
            log_and_execute(
                con,
                create_sql,
                success_msg,
                f"Error creating {entity_type} {entity_name}",
            )
        else:
            log.warning(f"{entity_type.capitalize()} {entity_name} already exists")


class DatabaseUtils:
    def __init__(self, **kwargs):
        """
        Initializes the DatabaseUtils object with the specified connection parameters.

        Parameters:
        **kwargs: The connection parameters for the database.
        """
        self.conn = None
        self.conn_args = kwargs
        self.log = log

    def __enter__(self):
        """
        Opens a connection to the database when entering a context.

        Returns:
        self: The DatabaseUtils object.
        """
        try:
            self.conn = psycopg.connect(**self.conn_args)
            self.conn.autocommit = True
            self.log.info(
                f"Connection to PostgreSQL successful. Using database [{self.conn_args.get('dbname')}]"
            )
        except Error as e:
            self.log.error(f"The error '{e}' occured when connecting to PostgreSQL")
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the connection to the database when exiting a context.

        Parameters:
        - exc_type, exc_val, exc_tb: Information about any exception that occurred in the context.
        """
        if self.conn is not None:
            self.conn.close()

    def execute_sql(self, command, ret=0):
        """
        Executes a SQL command.

        Parameters:
        - command (str): The SQL command to execute.
        - ret (int, optional): The number of rows to return. If 0 (default), no rows are returned.

        Returns:
        - list: The returned rows, if any.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(command)
                if ret == 0:
                    return
                elif ret == 1:
                    return cur.fetchone()[0]
                elif ret == 2:
                    return cur.fetchall()
        except Error as e:
            self.log.error(
                f"The error '{e}' occurred when communicating with the database"
            )
            raise

    def execute_sql_file(self, file_path):
        """
        Executes a SQL script from a file.

        Parameters:
        - file_path (str): The path to the SQL file.
        """
        with open(file_path, "r") as file:
            sql_commands = file.read()
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql_commands)
        except Error as e:
            self.log.error(
                f"The error '{e}' occurred when communicating with the database"
            )
            raise
