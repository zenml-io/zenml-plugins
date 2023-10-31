import sagemaker
import boto3

import os

REGION_NAME = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = REGION_NAME
ROLE_NAME = "hamza_connector"

auth_arguments = {
    "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
    "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
    "region_name": REGION_NAME,
}


iam = boto3.client("iam", **auth_arguments)
role = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]

session = sagemaker.Session(boto3.Session(**auth_arguments))

print(session)
