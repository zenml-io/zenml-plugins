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


import mlflow
from typing_extensions import Annotated
from zenml import step
from zenml.client import Client
from zenml.logger import get_logger

logger = get_logger(__name__)

model_registry = Client().active_stack.model_registry


@step
def promote_get_metric(
    name: str,
    metric: str,
    version: str,
) -> Annotated[float, "metric"]:
    """Get metric for comparison for promoting a model.

    This is an example of a metric retrieval step. It is used to retrieve
    a metric from an MLFlow run, that is linked to a model version in the
    model registry. This step is used in the `promote_model` pipeline.

    Args:
        name: Name of the model registered in the model registry.
        metric: Name of the metric to be retrieved.
        version: Version of the model to be retrieved.

    Returns:
        Metric value for a given model version.
    """

    ### ADD YOUR OWN CODE HERE - THIS IS JUST AN EXAMPLE ###
    model_version = model_registry.get_model_version(name=name, version=version)
    mlflow_run = mlflow.get_run(run_id=model_version.metadata.mlflow_run_id)
    logger.info("Getting metric from MLFlow run %s", mlflow_run.info.run_id)

    metric = mlflow_run.data.metrics.get(metric)
    ### YOUR CODE ENDS HERE ###
    return metric
