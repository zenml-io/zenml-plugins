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

from typing import List, Optional

from zenml import get_pipeline_context, pipeline
from zenml.client import Client
from zenml.logger import get_logger

from steps import (
    deploy_locally,
    deploy_to_huggingface,
    notify_on_failure,
    notify_on_success,
    save_model_to_deploy,
)

logger = get_logger(__name__)

# Get experiment tracker
orchestrator = Client().active_stack.orchestrator

# Check if orchestrator flavor is either default or skypilot
if orchestrator.flavor not in ["local"]:
    raise RuntimeError(
        "Your active stack needs to contain a default or skypilot orchestrator for "
        "the deployment pipeline to work."
    )


@pipeline(
    on_failure=notify_on_failure,
)
def nlp_use_case_deploy_pipeline(
    labels: Optional[List[str]] = ["Negative", "Positive"],
    title: Optional[str] = None,
    description: Optional[str] = None,
    model_name_or_path: Optional[str] = "model",
    tokenizer_name_or_path: Optional[str] = "tokenizer",
    interpretation: Optional[str] = None,
    example: Optional[str] = None,
    repo_name: Optional[str] = "nlp_use_case",
):
    """
    Model deployment pipeline.

    This pipelines deploys latest model on mlflow registry that matches
    the given stage, to one of the supported deployment targets.

    Args:
        labels: List of labels for the model.
        title: Title for the model.
        description: Description for the model.
        model_name_or_path: Name or path of the model.
        tokenizer_name_or_path: Name or path of the tokenizer.
        interpretation: Interpretation for the model.
        example: Example for the model.
        repo_name: Name of the repository to deploy to HuggingFace Hub.
    """
    ### ADD YOUR OWN CODE HERE - THIS IS JUST AN EXAMPLE ###
    # Link all the steps together by calling them and passing the output
    # of one step as the input of the next step.
    pipeline_extra = get_pipeline_context().extra

    ########## Save Model locally ##########
    save_model_to_deploy(
        mlflow_model_name=pipeline_extra["mlflow_model_name"],
        stage=pipeline_extra["target_env"],
    )
    ########## Deploy Locally ##########
    deploy_locally(
        labels=labels,
        title=title,
        description=description,
        interpretation=interpretation,
        example=example,
        model_name_or_path=model_name_or_path,
        tokenizer_name_or_path=tokenizer_name_or_path,
        after=["save_model_to_deploy"],
    )
    ########## Deploy to HuggingFace ##########
    deploy_to_huggingface(
        repo_name=repo_name,
        after=["save_model_to_deploy"],
    )
    last_step_name = "deploy_to_huggingface"

    notify_on_success(after=[last_step_name])
    ### YOUR CODE ENDS HERE ###
