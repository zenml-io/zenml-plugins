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

from gradio.aws_helper import get_sagemaker_role, get_sagemaker_session
from sagemaker.huggingface import HuggingFaceModel
from typing_extensions import Annotated
from zenml import get_step_context, step
from zenml.logger import get_logger
from zenml.model import DeploymentArtifactConfig

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
    deployment_metadata = mv.get_artifact_object(name="huggingface_url").metadata
    repo_id = deployment_metadata["repo_id"].value
    revision = deployment_metadata["revision"].value

    # Sagemaker
    role = get_sagemaker_role()
    session = get_sagemaker_session()

    hub = {
        "HF_MODEL_ID": repo_id,
        "HF_MODEL_REVISION": revision,
        "HF_TASK": "text-classification",
    }

    # Hugging Face Model Class
    huggingface_model = HuggingFaceModel(
        env=hub,
        role=role,  # iam role from AWS
        transformers_version="4.26.0",
        pytorch_version="1.13.1",
        py_version="py39",
        sagemaker_session=session,
    )

    # deploy model to SageMaker
    predictor = huggingface_model.deploy(
        initial_instance_count=1,  # number of instances
        instance_type="ml.g5.2xlarge",  #'ml.g5.4xlarge'
        container_startup_health_check_timeout=300,
    )
    endpoint_name = predictor.endpoint_name

    return endpoint_name
