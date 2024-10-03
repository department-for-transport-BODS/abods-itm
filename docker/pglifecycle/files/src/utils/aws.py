import boto3
import json
import re
from botocore.exceptions import ClientError
from .config import (
    AWS_REGION, 
    ENVIRONMENT, 
    PROJECT_NAME
)
from .logger import log
from os import makedirs, path, walk


def download_s3_dir(bucket_name: str, prefix_path: str, local_path: str):
    """
    Download objects from S3 prefix path to a local file.

    :param bucket_name: Name of the S3 bucket.
    :param prefix_path: Prefix path of the files to download.
    :param local_path: Local path to save the downloaded files.
    """

    session = boto3.session.Session()
    res = session.resource(
        service_name="s3",
        region_name=AWS_REGION
    )
    try:
        bucket = res.Bucket(bucket_name)
        if s3_dir_exists(bucket_name, prefix_path):
            for obj in bucket.objects.filter(Prefix=prefix_path+"/"):
                target = obj.key if local_path is None \
                    else path.join(local_path, path.relpath(obj.key, prefix_path))
                log.debug(f"Target is {target}")
                if not path.exists(path.dirname(target)):
                    makedirs(path.dirname(target))
                if obj.key[-1] == "/":
                    continue
                bucket.download_file(obj.key, target)
                log.debug(next(walk(local_path), (None, None, []))[2])
            log.info(f"Objects under '{prefix_path}' downloaded successfully to '{local_path}'")
        else:
            raise Exception("Error downloading directory contents from S3. Provided path does not exist")
    except ClientError as e:
        raise Exception(f"Error downloading directory contents from S3: {e}")


def generate_rds_iam_auth_token(host, port, username) -> str:
    """
    Generates an AWS RDS IAM authentication token for a given RDS instance.

    Parameters:
    - hostname (str): The endpoint of the RDS instance.
    - port (int): The port number for the RDS instance.
    - username (str): The database username.

    Returns:
    - str: The generated IAM authentication token if successful.
    - None: If an error occurs during token generation.
    """
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name="rds",
            region_name=AWS_REGION
        )
        token = client.generate_db_auth_token(
            DBHostname=host,
            DBUsername=username,
            Port=port
        )
        return token
    except Exception as e:
        log.error(f"An error occurred while generating the IAM auth token: {e}")
        return None


def get_latest_object_dir(bucket_name: str, prefix_path: str):
    """
    Retrieve the latest version of an object or prefix, using a given S3 bucket path.

    Args:
    - bucket_name: Name of the S3 bucket.
    - bucket_prefix: Prefix to search within the bucket.

    Returns:
    - The latest version number (string) if found, None otherwise.
    """

    session = boto3.session.Session()
    client = session.client(
        service_name="s3",
        region_name=AWS_REGION
    )
    try:
        response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix_path+"/", Delimiter="/")
        versioned_common_prefixes = [prefix["Prefix"] for prefix in response.get("CommonPrefixes", [])
                                      if re.match(r"^v[0-9]+(\.[0-9]+){2}$", prefix["Prefix"].split("/")[-2])]
        if not versioned_common_prefixes:
            log.error(f"No versioned objects have been found under the path {prefix_path}")
            return None
        version_numbers = [tuple(int(v) for v in prefix.split("/")[-2].split(".")) for prefix in versioned_common_prefixes]
        latest_version = max(version_numbers)
        latest_version = ".".join(str(v) for v in latest_version)
        return latest_version
    except ClientError as e:
        log.error(f"Error getting the latest version from S3: {e}")
        return None


def get_secret(secret_arn: str) -> str:
    """
    Retrieves the value of a secret specified by its ARN.

    Parameters:
    - secret_arn (str): The ARN of the secret to retrieve.

    Returns:
    - str: The value of the retrieved secret.
    """

    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=AWS_REGION
        )
        response = client.get_secret_value(SecretId=secret_arn)
        log.info('The specified secret was successfully retrieved')
        return json.loads(response['SecretString'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            log.error('The specified secret was not found')
        else:
            log.error(f'The error "{e}" occurred when retrieving the secret')
        raise


def s3_dir_exists(bucket_name: str, prefix_path: str) -> bool:
    """
    Check if an object exists in an S3 bucket.

    :param bucket_name: The name of the S3 bucket.
    :param prefix_path: Prefix path of the files to download.
    :return: True if the path exists, False otherwise.
    """

    session = boto3.session.Session()
    client = session.client(
        service_name="s3",
        region_name=AWS_REGION
    )
    try:
        client.list_objects(Bucket=bucket_name, Prefix=prefix_path, Delimiter="/", MaxKeys=1)
        log.info(f"Path '{prefix_path}' found in S3 bucket '{bucket_name}'")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            log.error(f"Path '{prefix_path}' does not exist under S3 bucket '{bucket_name}'")
            return False
        else:
            log.error("Something else went wrong: {e}")
            return False