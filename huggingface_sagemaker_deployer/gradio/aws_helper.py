import os

import boto3
import sagemaker

REGION_NAME = "us-east-1"
ROLE_NAME = "hamza_connector"
os.environ["AWS_DEFAULT_REGION"] = REGION_NAME

auth_arguments = {
    "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
    "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
    "aws_session_token": os.environ["AWS_SESSION_TOKEN"],
    "region_name": REGION_NAME,
}


def get_sagemaker_role():
    iam = boto3.client("iam", **auth_arguments)
    role = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    return role


def get_sagemaker_session():
    session = sagemaker.Session(boto3.Session(**auth_arguments))
    return session
