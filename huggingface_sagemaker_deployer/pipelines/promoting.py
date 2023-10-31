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


from zenml import get_pipeline_context, pipeline
from zenml.logger import get_logger

from steps import (
    notify_on_failure,
    notify_on_success,
    promote_get_metric,
    promote_get_versions,
    promote_metric_compare_promoter,
)

logger = get_logger(__name__)


@pipeline(
    on_failure=notify_on_failure,
)
def nlp_use_case_promote_pipeline():
    """
    Model promotion pipeline.

    This is a pipeline that promotes the best model to the chosen
    stage, e.g. Production or Staging. Based on a metric comparison
    between the latest and the currently promoted model version,
    or just the latest model version.
    """
    ### ADD YOUR OWN CODE HERE - THIS IS JUST AN EXAMPLE ###
    # Link all the steps together by calling them and passing the output
    # of one step as the input of the next step.
    pipeline_extra = get_pipeline_context().extra

    ########## Promotion stage ##########
    latest_version, current_version = promote_get_versions()
    latest_metric = promote_get_metric(
        name=pipeline_extra["mlflow_model_name"],
        metric="eval_loss",
        version=latest_version,
    )
    current_metric = promote_get_metric(
        name=pipeline_extra["mlflow_model_name"],
        metric="eval_loss",
        version=current_version,
    )

    promote_metric_compare_promoter(
        latest_metric=latest_metric,
        current_metric=current_metric,
        latest_version=latest_version,
        current_version=current_version,
    )
    last_step_name = "promote_metric_compare_promoter"

    notify_on_success(after=[last_step_name])
    ### YOUR CODE ENDS HERE ###
