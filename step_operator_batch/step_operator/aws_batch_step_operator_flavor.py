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

from abc import abstractmethod
from typing import Type

from zenml.stack import Flavor
from zenml.config.base_settings import BaseSettings
from zenml.step_operators import BaseStepOperator, BaseStepOperatorConfig
from typing import Optional


class AWSBatchStepOperatorSettings(BaseSettings):
    """Settings for the AWS Batch step operator.

    Attributes:
        

    """

    pass


class AWSBatchStepOperatorConfig(BaseStepOperatorConfig, AWSBatchStepOperatorSettings):
    """Config for the AWS Batch Step operator.

    Attributes:
        job_queue_name: The job queue where the job is submitted.
            You can specify either the name or the Amazon Resource Name (ARN) of the queue.
    """

    job_queue_name: str

    @property
    def is_remote(self) -> bool:
        """Checks if this stack component is running remotely.

        This designation is used to determine if the stack component can be
        used with a local ZenML database or if it requires a remote ZenML
        server.

        Returns:
            True if this config is for a remote component, False otherwise.
        """
        return True

class AWSBatchOperatorFlavor(Flavor):
    """Base class for all ZenML step operator flavors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the name of the flavor."""

    @property
    def config_class(self) -> Type[AWSBatchStepOperatorConfig]:
        """Returns the config class for this flavor."""
        return AWSBatchStepOperatorConfig

    @property
    @abstractmethod
    def implementation_class(self) -> Type[BaseStepOperator]:
        from step_operator.aws_batch_step_operator import AWSBatchStepOperator

        """Returns the implementation class for this flavor."""
        return AWSBatchStepOperator
