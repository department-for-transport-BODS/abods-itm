import psycopg
import re
from .logger import log
from os import getenv
from psycopg import Error
from utils.aws import get_secret, generate_rds_iam_auth_token
from utils.config import (
    ENVIRONMENT,
    POSTGRES_HOST,
    POSTGRES_PORT
)
from utils.logger import log


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
    conn_opts = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": "postgres"
    }
    log.debug(f"Default options for PostgreSQL connection: {conn_opts}")

    if ENVIRONMENT == "local":
        conn_opts.update({
            "user": getenv("POSTGRES_USER"),
            "password": getenv("POSTGRES_PASSWORD"),
            "gssencmode": "disable"
        })
    else:
        log.debug(f"Generating IAM authentication token for login against {POSTGRES_HOST}")
        username = ev["authUser"]
        token = generate_rds_iam_auth_token(POSTGRES_HOST, POSTGRES_PORT, username)
        if not token:
            log.error("Failed to generate IAM token. Exiting.")
            return None
        conn_opts.update({
            "user": username,
            "password": token,
            "sslmode": "require"
        })

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
    user_credentials = get_secret(credentials_arn) if ENVIRONMENT != "local" else {"username": "local", "password": "local"}
    sql = f"""CREATE USER MAPPING
    FOR {user_name}
    SERVER {server_name} 
    OPTIONS (user '{user_credentials["username"]}', password '{user_credentials["password"]}');
    GRANT USAGE ON FOREIGN SERVER {server_name} TO {user_name}"""
    return sql, f"User Mapping {user_name} for server {server_name} created successfully"


def create_user_sql(user):
    user_name = user["name"]
    role_name = user["roleName"] if "roleName" in user else re.sub(r"_[^_]+_", "_", user_name)
    auth_type = user["authType"]
    if auth_type == "scram":
        user_password = get_secret(user["credentialsArn"])["password"] if ENVIRONMENT != "local" else "local"
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


# def generate_connection_string(**kwargs) -> str:
#     user_password = ""
#     if kwargs.get("user"):
#         user_password += kwargs.get("user")
#         if kwargs.get("password"):
#             user_password += ":" + kwargs.get("password")
#         user_password += "@"

#     # Construct other parts
#     other_parts = ""
#     for key, value in kwargs.items():
#         if key not in ["host", "port", "user", "password", "dbname"] and value:
#             other_parts += f"{key}={value}&"

#     # Construct the final connection string
#     connection_string = f"postgresql://{user_password}{kwargs.get('host', '')}"
#     if kwargs.get("port"):
#         connection_string += f":{kwargs.get('port')}"
#     connection_string += f"/{kwargs.get('dbname', '')}"
#     if other_parts:
#         connection_string += f"?{other_parts[:-1]}"

#     return connection_string


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
            self.log.info(f"Connection to PostgreSQL successful. Using database [{self.conn_args.get('dbname')}]")
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
            self.log.error(f"The error '{e}' occurred when communicating with the database")
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
            self.log.error(f"The error '{e}' occurred when communicating with the database")
            raise