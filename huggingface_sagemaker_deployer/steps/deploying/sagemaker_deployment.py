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

# Initialize logger
logger = get_logger(__name__)


@step()
def deploy_hf_to_sagemaker() -> Annotated[str, "sagemaker_endpoint_name"]:
    """
    This step deploy the model to huggingface.

    Args:
        repo_name: The name of the repo to create/use on huggingface.
    """
    context = get_step_context()
    mv = context.model_config.get_or_create_model_version()
    breakpoint()
    print(mv.get_artifact_object(name="huggingface_url").metadata["endpoint"].value)
    print(mv.get_artifact_object(name="huggingface_url").metadata["repo_id"].value)
    print(mv.get_artifact_object(name="huggingface_url").metadata["revision"].value)
    print(mv.get_artifact_object(name="huggingface_url").metadata["path_in_repo"].value)
    return ""
