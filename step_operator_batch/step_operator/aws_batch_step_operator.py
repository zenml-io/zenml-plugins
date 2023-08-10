#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Implementation of the AWS Batch Step Operator."""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, cast

from zenml.client import Client
from zenml.config.build_configuration import BuildConfiguration
from step_operator.aws_batch_step_operator_flavor import (
    AWSBatchStepOperatorSettings,
    AWSBatchStepOperatorConfig,
)
from zenml.logger import get_logger
from zenml.stack import Stack, StackValidator
from zenml.step_operators import BaseStepOperator
from zenml.utils.string_utils import random_str

from typing import List
from zenml.step_operators import BaseStepOperator
from zenml.config.step_run_info import StepRunInfo
import boto3
import time

if TYPE_CHECKING:
    from zenml.config.base_settings import BaseSettings
    from zenml.config.step_run_info import StepRunInfo
    from zenml.models.pipeline_deployment_models import (
        PipelineDeploymentBaseModel,
    )

logger = get_logger(__name__)

BATCH_DOCKER_IMAGE_KEY = "sagemaker_step_operator"


class AWSBatchStepOperator(BaseStepOperator):
    """Class for the AWS Batch Step Operator"""

    @property
    def config(self) -> AWSBatchStepOperatorConfig:
        """Returns the config of the step operator.

        Returns:
            The config of the step operator.
        """
        return cast(AWSBatchStepOperatorConfig, self._config)
    
    def get_docker_builds(
        self, deployment: "PipelineDeploymentBaseModel"
    ) -> List["BuildConfiguration"]:
        """Gets the Docker builds required for the component.

        Args:
            deployment: The pipeline deployment for which to get the builds.

        Returns:
            The required Docker builds.
        """
        builds = []
        for step_name, step in deployment.step_configurations.items():
            if step.config.step_operator == self.name:
                build = BuildConfiguration(
                    key=BATCH_DOCKER_IMAGE_KEY,
                    settings=step.config.docker_settings,
                    step_name=step_name,
                )
                builds.append(build)

        return builds

    def launch(
            self,
            info: "StepRunInfo",
            entrypoint_command: List[str],
    ) -> None:
        """Abstract method to execute a step.

        Subclasses must implement this method and launch a **synchronous**
        job that executes the `entrypoint_command`.

        Args:
            info: Information about the step run.
            entrypoint_command: Command that executes the step.
        """
        if not info.config.resource_settings.empty:
            logger.warning(
                "Specifying custom step resources is not supported for "
                "the AWS Batch step operator. If you want to run this step "
                "operator on specific resources, you can do so by configuring "
                "a different instance type like this: "
                "`zenml step-operator update %s "
                "--instance_type=<INSTANCE_TYPE>`",
                self.name,
            )

        image_name = info.get_image(key=BATCH_DOCKER_IMAGE_KEY)

        settings = cast(AWSBatchStepOperatorSettings, self.get_settings(info))


        batch = boto3.client('batch')
        
        # Batch allows 63 characters at maximum for job name - ZenML uses 60 for safety margin.
        step_name = Client().get_run_step(info.step_run_id).name
        training_job_name = f"{info.pipeline.name}-{step_name}"[:55]
        suffix = random_str(4)
        unique_training_job_name = f"{training_job_name}-{suffix}"
        
        response = batch.register_job_definition(
            jobDefinitionName=unique_training_job_name,
            type='container',
            containerProperties={
                'image': image_name ,
                'command': entrypoint_command,
            }
        )

        job_definition = response['jobDefinitionName']

        response = batch.submit_job(
            jobName=unique_training_job_name,
            jobQueue=self.config.job_queue_name,
            jobDefinition=job_definition,
        )

        job_id = response['jobId']

        while True:
            response = batch.describe_jobs(jobs=[job_id])
            status = response['jobs'][0]['status']
            if status in ['SUCCEEDED', 'FAILED']:
                break
            time.sleep(10)
            print(f'Job completed with status {status}')
