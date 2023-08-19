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

import copy
import os
import sky
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union, cast, Tuple, Literal
from uuid import uuid4

from zenml.client import Client
from zenml.config.base_settings import BaseSettings
from zenml.entrypoints import StepEntrypointConfiguration
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
        instance_type: the instance type to use.
        cpus: the number of CPUs required for the task.
            If a str, must be a string of the form ``'2'`` or ``'2+'``, where
            the ``+`` indicates that the task requires at least 2 CPUs.
        memory: the amount of memory in GiB required. If a
            str, must be a string of the form ``'16'`` or ``'16+'``, where
            the ``+`` indicates that the task requires at least 16 GB of memory.
        accelerators: the accelerators required. If a str, must be
            a string of the form ``'V100'`` or ``'V100:2'``, where the ``:2``
            indicates that the task requires 2 V100 GPUs. If a dict, must be a
            dict of the form ``{'V100': 2}`` or ``{'tpu-v2-8': 1}``.
        accelerator_args: accelerator-specific arguments. For example,
            ``{'tpu_vm': True, 'runtime_version': 'tpu-vm-base'}`` for TPUs.
        use_spot: whether to use spot instances. If None, defaults to
            False.
        spot_recovery: the spot recovery strategy to use for the managed
            spot to recover the cluster from preemption. Refer to
            `recovery_strategy module <https://github.com/skypilot-org/skypilot/blob/master/sky/spot/recovery_strategy.py>`__ # pylint: disable=line-too-long
            for more details.
        region: the region to use.
        zone: the zone to use.
        image_id: the image ID to use. If a str, must be a string
            of the image id from the cloud, such as AWS:
            ``'ami-1234567890abcdef0'``, GCP:
            ``'projects/my-project-id/global/images/my-image-name'``;
            Or, a image tag provided by SkyPilot, such as AWS:
            ``'skypilot:gpu-ubuntu-2004'``. If a dict, must be a dict mapping
            from region to image ID, such as:

            .. code-block:: python

                {
                'us-west1': 'ami-1234567890abcdef0',
                'us-east1': 'ami-1234567890abcdef0'
                }

        disk_size: the size of the OS disk in GiB.
        disk_tier: the disk performance tier to use. If None, defaults to
            ``'medium'``.

        cluster_name: name of the cluster to create/reuse.  If None,
            auto-generate a name.
        retry_until_up: whether to retry launching the cluster until it is
            up.
        idle_minutes_to_autostop: automatically stop the cluster after this
            many minute of idleness, i.e., no running or pending jobs in the
            cluster's job queue. Idleness gets reset whenever setting-up/
            running/pending jobs are found in the job queue. Setting this
            flag is equivalent to running
            ``sky.launch(..., detach_run=True, ...)`` and then
            ``sky.autostop(idle_minutes=<minutes>)``. If not set, the cluster
            will not be autostopped.
        down: Tear down the cluster after all jobs finish (successfully or
            abnormally). If --idle-minutes-to-autostop is also set, the
            cluster will be torn down after the specified idle time.
            Note that if errors occur during provisioning/data syncing/setting
            up, the cluster will not be torn down for debugging purposes.
        stream_logs: if True, show the logs in the terminal.
    """

    # Resources
    instance_type: Optional[str] = None
    cpus: Union[None, int, float, str] = None
    memory: Union[None, int, float, str] = None
    accelerators: Union[None, str, Dict[str, int]] = None
    accelerator_args: Optional[Dict[str, str]] = None
    use_spot: Optional[bool] = None
    spot_recovery: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    image_id: Union[Dict[str, str], str, None] = None
    disk_size: Optional[int] = None
    disk_tier: Optional[Literal["high", "medium", "low"]] = None

    # Run settings
    cluster_name: Optional[str] = None
    retry_until_up: bool = False
    idle_minutes_to_autostop: Optional[int] = 30
    down: bool = True
    stream_logs: bool = True


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

        # Set up some variables for configuration
        orchestrator_run_id = str(uuid4())
        environment[ENV_ZENML_SKYPILOT_ORCHESTRATOR_RUN_ID] = orchestrator_run_id

        # Create the dag
        sky_dag = sky.Dag()
        
        for step_name, step in deployment.step_configurations.items():
            if self.requires_resources_in_orchestration_environment(step):
                logger.warning(
                    "Specifying step resources is not yet supported for "
                    "the Kubernetes orchestrator, ignoring resource "
                    "configuration for step %s.",
                    step_name,
                )

            assert stack.container_registry

            # Get Docker image for the orchestrator pod
            try:
                image = self.get_image(deployment=deployment)
            except KeyError:
                # If no generic pipeline image exists (which means all steps have
                # custom builds) we use a random step image as all of them include
                # dependencies for the active stack
                pipeline_step_name = next(iter(deployment.step_configurations))
                image = self.get_image(
                    deployment=deployment, step_name=pipeline_step_name
                )

            # Configure entrypoint and args
            entrypoint = StepEntrypointConfiguration.get_entrypoint_command()
            entrypoint_str = " ".join(entrypoint)
            arguments = StepEntrypointConfiguration.get_entrypoint_arguments(
                step_name=step_name, deployment_id=deployment.id
            )
            arguments_str = " ".join(arguments)

            # Set up docker run command
            docker_environment = {}
            docker_environment.update(environment)
            docker_environment_str = " ".join(
                f"-e {k}={v}" for k, v in docker_environment.items()
            )

            settings = cast(
                SkypilotOrchestratorSettings,
                self.get_settings(deployment),
            )
                    
            start_time = time.time()

            # Configure cloud and instance type
            cloud = None
            setup = None
            instance_type = None

            if "gs" in stack.artifact_store.config.path:
                cloud = sky.clouds.GCP()
                instance_type = settings.instance_type or "n1-standard-4"
            elif "s3" in stack.artifact_store.config.path:
                cloud = sky.clouds.AWS()
                instance_type = settings.instance_type or "t3.xlarge"
                setup = f"aws ecr get-login-password --region {stack.container_registry._get_region()} | docker login --username AWS --password-stdin {stack.container_registry.config.uri}"
            else:
                raise RuntimeError(
                    "Currently, SkyPilot only supports GCP and AWS artifact stores. Please use of these artifact stores in the active stack."
                )

            task = sky.Task(
                envs=docker_environment,
                run=f"docker run --rm {docker_environment_str} {image} {entrypoint_str} {arguments_str}",
                setup=setup,
            )
            task = task.set_resources(
                sky.Resources(
                    cloud=cloud,
                    instance_type=instance_type,
                    cpus=settings.cpus,
                    memory=settings.memory,
                    accelerators=settings.accelerators,
                    accelerator_args=settings.accelerator_args,
                    use_spot=settings.use_spot,
                    spot_recovery=settings.spot_recovery,
                    region=settings.region,
                    zone=settings.zone,
                    image_id=settings.image_id,
                    disk_size=settings.disk_size,
                    disk_tier=settings.disk_tier,
                )
            )

            sky_dag.add(task)

        # Resolve cluster
        cluster_name = settings.cluster_name
        if cluster_name is None:
            # Find existing cluster
            for i in sky.status():
                if type(i["handle"].launched_resources.cloud) is type(cloud):
                    cluster_name = i["handle"].cluster_name
                    logger.info(
                        f"Found existing cluster {cluster_name}. Reusing..."
                    )

        try:
            sky.launch(
                sky_dag,
                cluster_name,
                retry_until_up=settings.retry_until_up,
                idle_minutes_to_autostop=settings.idle_minutes_to_autostop,
                down=settings.down,
                stream_logs=settings.stream_logs,
            )
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
