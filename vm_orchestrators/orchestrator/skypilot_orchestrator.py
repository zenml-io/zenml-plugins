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
"""Implementation of the a Skypilot based VM orchestrator."""


import json
import copy
import os
import sky
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union, cast, Tuple
from uuid import uuid4

from docker.errors import ContainerError
from pydantic import validator

from zenml.client import Client
from zenml.config.base_settings import BaseSettings
from zenml.entrypoints import PipelineEntrypointConfiguration
from zenml.enums import StackComponentType
from zenml.logger import get_logger
from zenml.orchestrators import (
    BaseOrchestratorConfig,
    BaseOrchestratorFlavor,
    ContainerizedOrchestrator,
)
from zenml.orchestrators import utils as orchestrator_utils
from zenml.stack import Stack, StackValidator
from zenml.utils import string_utils

if TYPE_CHECKING:
    from zenml.models.pipeline_deployment_models import (
        PipelineDeploymentResponseModel,
    )

logger = get_logger(__name__)

ENV_ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID = "ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID"


class SkypilotOrchestratorSettings(BaseSettings):
    """Skypilot orchestrator settings.

    Attributes:
        run_args: Arguments to pass to the `docker run` call. (See
            https://docker-py.readthedocs.io/en/stable/containers.html for a list
            of what can be passed.)
    """

    run_args: Dict[str, Any] = {}

    @validator("run_args", pre=True)
    def _convert_json_string(
        cls, value: Union[None, str, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Converts potential JSON strings passed via the CLI to dictionaries.

        Args:
            value: The value to convert.

        Returns:
            The converted value.

        Raises:
            TypeError: If the value is not a `str`, `Dict` or `None`.
            ValueError: If the value is an invalid json string or a json string
                that does not decode into a dictionary.
        """
        if isinstance(value, str):
            try:
                dict_ = json.loads(value)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid json string '{value}'") from e

            if not isinstance(dict_, Dict):
                raise ValueError(
                    f"Json string '{value}' did not decode into a dictionary."
                )

            return dict_
        elif isinstance(value, Dict) or value is None:
            return value
        else:
            raise TypeError(f"{value} is not a json string or a dictionary.")


class SkypilotOrchestratorConfig(  # type: ignore[misc] # https://github.com/pydantic/pydantic/issues/4173
    BaseOrchestratorConfig, SkypilotOrchestratorSettings
):
    """Skypilot orchestrator config."""

    @property
    def is_local(self) -> bool:
        """Checks if this stack component is running locally.

        This designation is used to determine if the stack component can be
        shared with other users or if it is only usable on the local host.

        Returns:
            True if this config is for a local component, False otherwise.
        """
        return False


class SkypilotOrchestratorFlavor(BaseOrchestratorFlavor):
    """Flavor for the Skypilot orchestrator."""

    @property
    def name(self) -> str:
        """Name of the orchestrator flavor.

        Returns:
            Name of the orchestrator flavor.
        """
        return "vm_orchestrator"

    @property
    def docs_url(self) -> Optional[str]:
        """A url to point at docs explaining this flavor.

        Returns:
            A flavor docs url.
        """
        return self.generate_default_docs_url()

    @property
    def sdk_docs_url(self) -> Optional[str]:
        """A url to point at SDK docs explaining this flavor.

        Returns:
            A flavor SDK docs url.
        """
        return self.generate_default_sdk_docs_url()

    @property
    def logo_url(self) -> str:
        """A url to represent the flavor in the dashboard.

        Returns:
            The flavor logo.
        """
        return "https://skypilot.readthedocs.io/en/v0.2.0/_images/skypilot-wide-light-1k.png"

    @property
    def config_class(self) -> Type[BaseOrchestratorConfig]:
        """Config class for the base orchestrator flavor.

        Returns:
            The config class.
        """
        return SkypilotOrchestratorConfig

    @property
    def implementation_class(self) -> Type["SkypilotOrchestrator"]:
        """Implementation class for this flavor.

        Returns:
            Implementation class for this flavor.
        """
        return SkypilotOrchestrator


class SkypilotOrchestrator(ContainerizedOrchestrator):
    """Orchestrator responsible for running pipelines remotely in a VM.

    This orchestrator does not support running on a schedule.
    """

    @property
    def config(self) -> SkypilotOrchestratorConfig:
        """Returns the `SkypilotOrchestratorConfig` config.

        Returns:
            The configuration.
        """
        return cast(SkypilotOrchestratorConfig, self._config)

    @property
    def validator(self) -> Optional[StackValidator]:
        """Validates the stack.

        In the remote case, checks that the stack contains a container registry,
        image builder and only remote components.

        Returns:
            A `StackValidator` instance.
        """

        def _validate_remote_components(
            stack: "Stack",
        ) -> Tuple[bool, str]:
            for component in stack.components.values():
                if not component.config.is_local:
                    continue

                return False, (
                    f"The Skypilot orchestrator runs pipelines remotely, "
                    f"but the '{component.name}' {component.type.value} is "
                    "a local stack component and will not be available in "
                    "the Skypilot step.\nPlease ensure that you always "
                    "use non-local stack components with the Skypilot "
                    "orchestrator."
                )

            return True, ""

        return StackValidator(
            required_components={
                StackComponentType.CONTAINER_REGISTRY,
                StackComponentType.IMAGE_BUILDER,
            },
            custom_validation_function=_validate_remote_components,
        )

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the Skypilot orchestrator.

        Returns:
            The settings class.
        """
        return SkypilotOrchestratorSettings

    @property
    def validator(self) -> Optional[StackValidator]:
        """Ensures there is an image builder in the stack.

        Returns:
            A `StackValidator` instance.
        """
        return StackValidator(required_components={StackComponentType.IMAGE_BUILDER})

    def get_orchestrator_run_id(self) -> str:
        """Returns the active orchestrator run id.

        Raises:
            RuntimeError: If the environment variable specifying the run id
                is not set.

        Returns:
            The orchestrator run id.
        """
        try:
            return os.environ[ENV_ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID]
        except KeyError:
            raise RuntimeError(
                "Unable to read run id from environment variable "
                f"{ENV_ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID}."
            )

    def prepare_or_run_pipeline(
        self,
        deployment: "PipelineDeploymentResponseModel",
        stack: "Stack",
        environment: Dict[str, str],
    ) -> Any:
        """Runs all pipeline steps in Skypilot containers.

        Args:
            deployment: The pipeline deployment to prepare or run.
            stack: The stack the pipeline will run on.
            environment: Environment variables to set in the orchestration
                environment.

        Raises:
            RuntimeError: If a step fails.
        """
        if deployment.schedule:
            logger.warning(
                "Skypilot Orchestrator currently does not support the"
                "use of schedules. The `schedule` will be ignored "
                "and the pipeline will be run immediately."
            )

        orchestrator_run_id = str(uuid4())
        environment[ENV_ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID] = orchestrator_run_id

        settings = cast(
            SkypilotOrchestratorSettings,
            self.get_settings(deployment),
        )

        entrypoint = PipelineEntrypointConfiguration.get_entrypoint_command()
        entrypoint_str = " ".join(entrypoint)
        arguments = PipelineEntrypointConfiguration.get_entrypoint_arguments(
            deployment_id=deployment.id
        )
        arguments_str = " ".join(arguments)

        image = self.get_image(deployment=deployment)

        run_args = copy.deepcopy(settings.run_args)
        docker_environment = run_args.pop("environment", {})
        docker_environment.update(environment)
        docker_environment_str = " ".join(
            f"-e {k}={v}" for k, v in docker_environment.items()
        )

        start_time = time.time()

        # Choose any
        cloud = None
        setup = None
        instance_type = None

        if "gs" in stack.artifact_store.config.path:
            cloud = sky.clouds.GCP()
            instance_type = "n1-standard-4"
        elif "s3" in stack.artifact_store.config.path:
            cloud = sky.clouds.AWS()
            instance_type = "t3.xlarge"
            setup = f"aws ecr get-login-password --region {stack.container_registry._get_region()} | docker login --username AWS --password-stdin {stack.container_registry.config.uri}"
        # Run the entire pipeline
        try:
            task = sky.Task(
                envs=docker_environment,
                run=f"docker run --rm {docker_environment_str} {image} {entrypoint_str} {arguments_str}",
                setup=setup,
            )
            task = task.set_resources(
                sky.Resources(
                    cloud=cloud,
                    instance_type=instance_type,
                )
            )

            # Find cluster if exist
            cluster_name = None
            for i in sky.status():
                if type(i["handle"].launched_resources.cloud) is type(cloud):
                    cluster_name = i["handle"].cluster_name
                    logger.info(f"Found existing cluster {cluster_name}. Reusing...")

            sky.launch(task, cluster_name, retry_until_up=True)

        except Exception as e:
            raise RuntimeError(e)

        run_duration = time.time() - start_time
        run_id = orchestrator_utils.get_run_id_for_orchestrator_run_id(
            orchestrator=self, orchestrator_run_id=orchestrator_run_id
        )
        run_model = Client().zen_store.get_run(run_id)
        logger.info(
            "Pipeline run `%s` has finished in `%s`.\n",
            run_model.name,
            string_utils.get_human_readable_time(run_duration),
        )
