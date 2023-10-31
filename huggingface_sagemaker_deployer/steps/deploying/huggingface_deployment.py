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
from typing_extensions import Annotated
from huggingface_hub import HfApi
from zenml import step, log_artifact_metadata
from zenml.client import Client
from zenml.logger import get_logger

# Initialize logger
logger = get_logger(__name__)


@step()
def deploy_to_huggingface(
    repo_name: str,
) -> Annotated[str, "huggingface_url"]:
    """
    This step deploy the model to huggingface.

    Args:
        repo_name: The name of the repo to create/use on huggingface.
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
        repo_id=repo_name, repo_type="model", exist_ok=True
    )
    zenml_repo_root = Client().root
    if not zenml_repo_root:
        logger.warning(
            "You're running the `deploy_to_huggingface` step outside of a ZenML repo."
            "Since the deployment step to huggingface is all about pushing the repo to huggingface, "
            "this step will not work outside of a ZenML repo where the gradio folder is present."
        )
        raise
    gradio_folder_path = os.path.join(zenml_repo_root, "gradio")
    url = api.upload_folder(
        folder_path=gradio_folder_path,
        repo_id=hf_repo.repo_id,
        repo_type="model",
    )
    # split the string by '/'
    url_split = url.split("/")

    # the resulting list would look like this: ['{self.endpoint}', '{repo_id}', 'tree', '{revision}', '{path_in_repo}']

    # now assign each split string to a variable
    endpoint = url_split[0][1:-1]  # remove the curly brackets
    repo_id = url_split[1][1:-1]  # remove the curly brackets
    # skip 'tree'
    revision = url_split[3][1:-1]  # remove the curly brackets
    path_in_repo = url_split[4][1:-1]  # remove the curly brackets

    log_artifact_metadata(
        output_name="None",
        endpoint=endpoint,
        repo_id=repo_id,
        revision=revision,
        path_in_repo=path_in_repo,
    )

    logger.info(f"Model updated: {url}")
    ### YOUR CODE ENDS HERE ###

    return url
