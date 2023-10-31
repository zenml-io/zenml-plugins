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

import os

from huggingface_hub import HfApi
from zenml import step, get_step_context
from zenml.enums import ModelStages
from zenml.client import Client
from zenml.logger import get_logger
from zenml.model import ModelArtifactConfig
from typing import Optional

from transformers import (
    PreTrainedModel,
    PreTrainedTokenizerBase,
)
from zenml import step
from zenml import step, pipeline, log_artifact_metadata, get_step_context
from zenml.model import ModelConfig

from zenml.logger import get_logger

# Initialize logger
logger = get_logger(__name__)



@step
def register_model(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    repo_name: Optional[str] = "model",
):
    """
    Register model to Huggingface.

    This step takes in a model and tokenizer artifact previously loaded and pre-processed by
    other steps in your pipeline, then registers the model to Huggingface Hub.

    Model training steps should have caching disabled if they are not deterministic
    (i.e. if the model training involve some random processes like initializing
    weights or shuffling data that are not controlled by setting a fixed random seed).

    Args:
        model: The model.
        tokenizer: The tokenizer.

    Returns:
        The trained model and tokenizer.
    """
    ### ADD YOUR OWN CODE HERE - THIS IS JUST AN EXAMPLE ###
    secret = Client().get_secret("huggingface_creds")
        
    assert (
        secret
    ), "No secret found with name 'huggingface_creds'. Please create one with your `username` and `token`."
    huggingface_username = secret.secret_values["username"]
    token = secret.secret_values["token"]
    api = HfApi(token=token)
    hf_repo = api.create_repo(
        repo_id=repo_name, repo_type="space", space_sdk="gradio", exist_ok=True
    )
    zenml_repo_root = Client().root
    if not zenml_repo_root:
        logger.warning(
            "You're running the `deploy_to_huggingface` step outside of a ZenML repo."
            "Since the deployment step to huggingface is all about pushing the repo to huggingface, "
            "this step will not work outside of a ZenML repo where the gradio folder is present."
        )
        raise
    
    log_artifact_metadata()
    
    gradio_folder_path = os.path.join(zenml_repo_root, "gradio")
    space = api.upload_folder(
        folder_path=gradio_folder_path,
        repo_id=hf_repo.repo_id,
        repo_type="space",
    )
    logger.info(f"Space created: {space}")
    ### YOUR CODE ENDS HERE ###
