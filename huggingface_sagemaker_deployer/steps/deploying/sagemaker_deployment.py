# Apache Software License 2.0
#
# Copyright (c) ZenML GmbH 2023. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from typing_extensions import Annotated
from zenml import step, get_step_context
from zenml.logger import get_logger
from zenml.model import DeploymentArtifactConfig
from sagemaker.huggingface import get_huggingface_llm_image_uri
from sagemaker.huggingface import HuggingFaceModel
import sagemaker
import boto3

import os
import time

# Initialize logger
logger = get_logger(__name__)


@step
def deploy_hf_to_sagemaker() -> (
    Annotated[str, "sagemaker_endpoint_name", DeploymentArtifactConfig()]
):
    """
    This step deploy the model to huggingface.

    Args:
        repo_name: The name of the repo to create/use on huggingface.
    """
    context = get_step_context()
    mv = context.model_config.get_or_create_model_version()
    repo_id = mv.get_artifact_object(name="huggingface_url").metadata["repo_id"].value
    revision = mv.get_artifact_object(name="huggingface_url").metadata["revision"].value

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

    # image uri
    llm_image = get_huggingface_llm_image_uri("huggingface")

    # Falcon 7b
    hub = {"HF_MODEL_ID": repo_id, "HF_MODEL_REVISION": revision}

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
    endpoint_name = predictor.endpoint_name

    time.sleep(10)

    # DELETE ENDPOINT to avoid unnecessary expenses
    predictor.delete_model()
    predictor.delete_endpoint()
    return endpoint_name
