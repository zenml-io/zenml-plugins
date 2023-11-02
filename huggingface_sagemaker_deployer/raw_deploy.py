import os

import boto3
import sagemaker

REGION_NAME = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = REGION_NAME
ROLE_NAME = "hamza_connector"

auth_arguments = {
    "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
    "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
    "aws_session_token": os.environ["AWS_SESSION_TOKEN"],
    "region_name": REGION_NAME,
}


iam = boto3.client("iam", **auth_arguments)
role = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]

session = sagemaker.Session(boto3.Session(**auth_arguments))

print(session)


from sagemaker.huggingface import get_huggingface_llm_image_uri

# image uri
llm_image = get_huggingface_llm_image_uri("huggingface")

print(f"image uri: {llm_image}")


from sagemaker.huggingface import HuggingFaceModel

# Falcon 7b
hub = {"HF_MODEL_ID": model_id, "HF_MODEL_REVISION": revision}

# Hugging Face Model Class
huggingface_model = HuggingFaceModel(
    env=hub,
    role=role,  # iam role from AWS
    image_uri=llm_image,
    sagemaker_session=session,
)

# deploy model to SageMaker
predictor = huggingface_model.deploy(
    initial_instance_count=1,  # number of instances
    instance_type="ml.g5.2xlarge",  #'ml.g5.4xlarge'
    container_startup_health_check_timeout=300,
)

import time

time.sleep(10)

# DELETE ENDPOINT to avoid unnecessary expenses
predictor.delete_model()
predictor.delete_endpoint()
