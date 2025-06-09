#  Copyright (c) ZenML GmbH 2025. All Rights Reserved.
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
"""Implementation of a custom Modal orchestrator."""

import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast
from uuid import uuid4

try:
    import modal
except ImportError:
    modal = None

from zenml.client import Client
from zenml.config.base_settings import BaseSettings
from zenml.config.build_configuration import BuildConfiguration
from zenml.config.resource_settings import ByteUnit, ResourceSettings
from zenml.enums import StackComponentType
from zenml.logger import get_logger
from zenml.orchestrators import (
    BaseOrchestratorConfig,
    BaseOrchestratorFlavor,
    ContainerizedOrchestrator,
)
from zenml.stack import Stack, StackValidator
from zenml.utils import string_utils

if TYPE_CHECKING:
    from zenml.models import PipelineDeploymentResponse, PipelineRunResponse

logger = get_logger(__name__)

ENV_ZENML_MODAL_ORCHESTRATOR_RUN_ID = "ZENML_MODAL_ORCHESTRATOR_RUN_ID"



def run_step_in_modal(
    step_name: str,
    deployment_id: str,
    orchestrator_run_id: str,
) -> None:
    """Execute a single ZenML step in Modal."""
    import os
    import subprocess
    import sys
    
    print(f"🚀 Running step '{step_name}' in Modal")
    sys.stdout.flush()
    
    # Set the orchestrator run ID in the Modal environment
    os.environ["ZENML_MODAL_ORCHESTRATOR_RUN_ID"] = orchestrator_run_id
    
    try:
        from zenml.entrypoints import StepEntrypointConfiguration
        
        # Get the entrypoint command and arguments
        entrypoint = StepEntrypointConfiguration.get_entrypoint_command()
        arguments = StepEntrypointConfiguration.get_entrypoint_arguments(
            step_name=step_name, deployment_id=deployment_id
        )
        
        # Execute the step
        command = entrypoint + arguments
        print(f"🔧 Executing: {' '.join(command)}")
        sys.stdout.flush()
        
        # Run the step with real-time output
        result = subprocess.run(
            command,
            env=os.environ.copy(),
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Step {step_name} failed with return code {result.returncode}")
            sys.stdout.flush()
            raise RuntimeError(
                f"Step {step_name} failed with return code {result.returncode}"
            )
        else:
            print(f"✅ Step {step_name} completed successfully")
            sys.stdout.flush()
            
    except Exception as e:
        print(f"💥 Error executing step {step_name}: {e}")
        sys.stdout.flush()
        raise


def get_gpu_values(
    settings: "ModalOrchestratorSettings", resource_settings: ResourceSettings
) -> Optional[str]:
    """Get the GPU values for the Modal orchestrator.

    Args:
        settings: The Modal orchestrator settings.
        resource_settings: The resource settings.

    Returns:
        The GPU string if a count is specified, otherwise the GPU type.
    """
    if not settings.gpu:
        return None
    # Prefer resource_settings gpu_count, fallback to 1
    gpu_count = resource_settings.gpu_count or 1
    return f"{settings.gpu}:{gpu_count}" if gpu_count > 1 else settings.gpu


def get_resource_values(
    config: "ModalOrchestratorConfig", resource_settings: ResourceSettings
) -> tuple[Optional[int], Optional[int]]:
    """Get CPU and memory values with config fallbacks.

    Args:
        config: The Modal orchestrator config.
        resource_settings: The resource settings.

    Returns:
        Tuple of (cpu_count, memory_mb) with config fallbacks.
    """
    # Prefer pipeline resource settings, fallback to config defaults
    cpu_count = resource_settings.cpu_count or config.cpu_count
    
    # Convert memory to MB if needed
    memory_mb = config.memory_mb
    if resource_settings.memory:
        memory_mb = int(resource_settings.get_memory(ByteUnit.MB))
    
    return cpu_count, memory_mb


def get_or_deploy_persistent_modal_app(
    pipeline_name: str,
    zenml_image: modal.Image,
    gpu_values: Optional[str],
    cpu_count: Optional[int],
    memory_mb: Optional[int],
    cloud: Optional[str],
    region: Optional[str],
    timeout: int,
    min_containers: Optional[int],
    max_containers: Optional[int],
    environment_name: Optional[str] = None,
) -> modal.Function:
    """Get or deploy a persistent Modal app with warm containers.
    
    This function deploys a Modal app that stays alive with warm containers
    for maximum speed between pipeline runs.
    """
    # Use pipeline name as app name for easy identification and reuse
    app_name = f"zenml-{pipeline_name.replace('_', '-')}"
    
    logger.info(f"🏗️  Getting/deploying persistent Modal app: {app_name}")
    
    # Create the app
    app = modal.App(app_name)
    
    # Ensure we have minimum containers for fast startup
    effective_min_containers = min_containers or 1
    effective_max_containers = max_containers or 10
    
    # Create the step execution function with warm containers for speed
    execute_step_func = app.function(
        image=zenml_image,
        gpu=gpu_values,
        cpu=cpu_count,
        memory=memory_mb,
        cloud=cloud,
        region=region,
        timeout=timeout,
        min_containers=effective_min_containers,  # Keep containers warm for speed
        max_containers=effective_max_containers,  # Allow scaling
    )(run_step_in_modal)
    
    # Try to lookup existing deployed app first, only deploy if truly doesn't exist
    try:
        logger.info(f"🔍 Checking for existing Modal app: {app_name}")
        
        # Check if app already exists and is deployed
        try:
            modal.App.lookup(app_name, environment_name=environment_name or "main")
            logger.info(f"♻️  Found existing deployed app '{app_name}' - reusing warm containers!")
            logger.info("🔥 Existing app has warm containers ready for immediate use!")
            
            # Try to lookup the function directly using Function.from_name (Modal 1.0)
            try:
                existing_function = modal.Function.from_name(app_name, "run_step_in_modal", environment_name=environment_name or "main")
                logger.info("✅ Successfully retrieved function from existing deployed app!")
                return existing_function
            except Exception as func_lookup_error:
                logger.warning(f"⚠️  Function lookup failed: {func_lookup_error}")
                logger.info("📝 Will deploy new version to ensure function is available")
                # Fall through to deployment
            
        except modal.exception.NotFoundError:
            # App doesn't exist, proceed with deployment
            logger.info(f"🆕 App '{app_name}' not found, deploying new app...")
        
        # Deploy new app only if lookup failed
        app.deploy(name=app_name, environment_name=environment_name or "main")
        logger.info(f"✅ App '{app_name}' deployed with {effective_min_containers} warm containers")
        
    except Exception as e:
        logger.warning(f"⚠️  Deployment issue: {e}")
        # Continue anyway - function should still work
    
    logger.info(f"🔥 Modal app configured for SPEED with min_containers={effective_min_containers}, max_containers={effective_max_containers}")
    logger.info(f"💡 This means {effective_min_containers} containers will stay warm for faster execution!")
    
    return execute_step_func


class ModalOrchestrator(ContainerizedOrchestrator):
    """Orchestrator responsible for running entire pipelines on Modal.

    This orchestrator runs complete pipelines in a single Modal function
    for maximum speed and efficiency, avoiding the overhead of multiple
    step executions.
    """

    @property
    def config(self) -> "ModalOrchestratorConfig":
        """Returns the Modal orchestrator config.

        Returns:
            The Modal orchestrator config.
        """
        return cast("ModalOrchestratorConfig", self._config)

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the Modal orchestrator.

        Returns:
            The settings class.
        """
        return ModalOrchestratorSettings

    def _setup_modal_client(self) -> None:
        """Setup Modal client with authentication."""
        if self.config.token:
            # Set Modal token from config
            os.environ["MODAL_TOKEN_ID"] = self.config.token
            logger.info("Using Modal token from orchestrator config")
        else:
            logger.info("Using default Modal authentication (~/.modal.toml)")
        
        # Set workspace/environment if provided
        if self.config.workspace:
            os.environ["MODAL_WORKSPACE"] = self.config.workspace
        if self.config.environment:
            os.environ["MODAL_ENVIRONMENT"] = self.config.environment

    @property
    def validator(self) -> Optional[StackValidator]:
        """Ensures there is a container registry and artifact store in the stack.

        Returns:
            A `StackValidator` instance.
        """
        def _validate_remote_components(stack: "Stack") -> tuple[bool, str]:
            if stack.artifact_store.config.is_local:
                return False, (
                    "The Modal orchestrator runs code remotely and "
                    "needs to write files into the artifact store, but the "
                    f"artifact store `{stack.artifact_store.name}` of the "
                    "active stack is local. Please ensure that your stack "
                    "contains a remote artifact store when using the Modal "
                    "orchestrator."
                )

            container_registry = stack.container_registry
            assert container_registry is not None

            if container_registry.config.is_local:
                return False, (
                    "The Modal orchestrator runs code remotely and "
                    "needs to push/pull Docker images, but the "
                    f"container registry `{container_registry.name}` of the "
                    "active stack is local. Please ensure that your stack "
                    "contains a remote container registry when using the "
                    "Modal orchestrator."
                )

            return True, ""

        return StackValidator(
            required_components={
                StackComponentType.CONTAINER_REGISTRY,
                StackComponentType.IMAGE_BUILDER,
            },
            custom_validation_function=_validate_remote_components,
        )

    def get_orchestrator_run_id(self) -> str:
        """Returns the active orchestrator run id.

        Raises:
            RuntimeError: If the environment variable specifying the run id
                is not set.

        Returns:
            The orchestrator run id.
        """
        try:
            return os.environ[ENV_ZENML_MODAL_ORCHESTRATOR_RUN_ID]
        except KeyError:
            raise RuntimeError(
                "Unable to read run id from environment variable "
                f"{ENV_ZENML_MODAL_ORCHESTRATOR_RUN_ID}."
            )

    def get_docker_builds(
        self, deployment: "PipelineDeploymentResponse"
    ) -> List["BuildConfiguration"]:
        """Get the Docker build configurations for the Modal orchestrator.

        Args:
            deployment: The pipeline deployment.

        Returns:
            A list of Docker build configurations.
        """
        # Use the standard containerized orchestrator build logic
        # This ensures ZenML builds the image with all pipeline code
        return super().get_docker_builds(deployment)

    def _build_modal_image(
        self,
        deployment: "PipelineDeploymentResponse",
        stack: "Stack",
        environment: Dict[str, str],
    ) -> modal.Image:
        """Build the Modal image for pipeline execution.

        Args:
            deployment: The pipeline deployment.
            stack: The stack the pipeline will run on.
            environment: Environment variables to set.

        Returns:
            The configured Modal image.

        Raises:
            RuntimeError: If no Docker credentials are found.
            ValueError: If no container registry is found.
        """
        # Get the ZenML-built image that contains all pipeline code
        image_name = self.get_image(deployment=deployment)

        if not stack.container_registry:
            raise ValueError(
                "No Container registry found in the stack. "
                "Please add a container registry and ensure "
                "it is correctly configured."
            )

        if docker_creds := stack.container_registry.credentials:
            docker_username, docker_password = docker_creds
        else:
            raise RuntimeError(
                "No Docker credentials found for the container registry."
            )

        # Create Modal secret for registry authentication
        registry_secret = modal.Secret.from_dict(
            {
                "REGISTRY_USERNAME": docker_username,
                "REGISTRY_PASSWORD": docker_password,
            }
        )

        # Build Modal image from the ZenML-built image
        # Use from_registry to pull the ZenML image with authentication
        # and install Modal dependencies
        zenml_image = (
            modal.Image.from_registry(
                image_name,
                secret=registry_secret
            )
            .pip_install("modal")  # Install Modal in the container
            .env(environment)
        )

        return zenml_image

    def prepare_or_run_pipeline(
        self,
        deployment: "PipelineDeploymentResponse",
        stack: "Stack",
        environment: Dict[str, str],
        placeholder_run: Optional["PipelineRunResponse"] = None,
    ) -> Any:
        """Runs the complete pipeline in a single Modal function.

        Args:
            deployment: The pipeline deployment to prepare or run.
            stack: The stack the pipeline will run on.
            environment: Environment variables to set in the orchestration
                environment.
            placeholder_run: An optional placeholder run for the deployment.

        Raises:
            RuntimeError: If a step fails.
        """
        if modal is None:
            raise RuntimeError(
                "Modal is not installed. Please install it with: pip install modal"
            )
        if deployment.schedule:
            logger.warning(
                "Modal Orchestrator currently does not support the "
                "use of schedules. The `schedule` will be ignored "
                "and the pipeline will be run immediately."
            )

        # Setup Modal authentication
        self._setup_modal_client()

        # Generate orchestrator run ID
        orchestrator_run_id = str(uuid4())
        environment[ENV_ZENML_MODAL_ORCHESTRATOR_RUN_ID] = orchestrator_run_id

        # Get settings from the first step (all steps use same Modal resources)
        first_step = list(deployment.step_configurations.values())[0]
        settings = cast(ModalOrchestratorSettings, self.get_settings(first_step))
        resource_settings = first_step.config.resource_settings

        # Build Modal image
        zenml_image = self._build_modal_image(deployment, stack, environment)

        # Configure resources with config fallbacks
        gpu_values = get_gpu_values(settings, resource_settings)
        cpu_count, memory_mb = get_resource_values(self.config, resource_settings)

        start_time = time.time()

        # Execute steps using Modal's fast container spin-up with PERSISTENT app
        logger.info("🚀 Starting pipeline execution with PERSISTENT Modal functions...")
        
        step_names = list(deployment.step_configurations.keys())
        logger.info(f"📋 Found {len(step_names)} steps: {step_names}")
        
        # Get or deploy persistent Modal app with BLAZING FAST warm containers
        execute_step = get_or_deploy_persistent_modal_app(
            pipeline_name=deployment.pipeline_configuration.name,
            zenml_image=zenml_image,
            gpu_values=gpu_values,
            cpu_count=cpu_count or 8,      # Default to 8 CPU cores for speed
            memory_mb=memory_mb or 16384,  # Default to 16GB RAM for speed
            cloud=settings.cloud or self.config.cloud,
            region=settings.region or self.config.region,
            timeout=self.config.timeout,
            min_containers=self.config.min_containers or 1,  # Keep 1 warm container for sequential execution
            max_containers=self.config.max_containers or 10,  # Scale to 10 containers
            environment_name=settings.environment or self.config.environment,  # Use environment from config/settings
        )
        
        logger.info("⚡ Executing steps with DEPLOYED Modal app and warm containers...")
        
        
        # Execute steps using the deployed app (no ephemeral context manager!)
        for step_name in step_names:
            logger.info(f"🏃‍♂️ Launching step '{step_name}' using deployed Modal function...")
            try:
                # Use the deployed function directly - no app.run() context needed!
                execute_step.remote(
                    step_name, 
                    deployment.id, 
                    orchestrator_run_id
                )
                logger.info(f"✅ Step '{step_name}' completed successfully")
            except Exception as e:
                logger.error(f"❌ Step '{step_name}' failed: {e}")
                raise

        run_duration = time.time() - start_time

        # Log completion
        logger.info(
            "Pipeline run has finished in `%s`.",
            string_utils.get_human_readable_time(run_duration),
        )


class ModalOrchestratorSettings(BaseSettings):
    """Modal orchestrator settings.

    Attributes:
        gpu: The type of GPU to use for the pipeline execution.
        region: The region to use for the pipeline execution.
        cloud: The cloud provider to use for the pipeline execution.
        environment: The Modal environment to use for the pipeline execution.
        cpu_count: Number of CPU cores to allocate.
        memory_mb: Memory in MB to allocate.
        timeout: Maximum execution time in seconds (default 24h).
        min_containers: Minimum containers to keep warm (replaces keep_warm).
        max_containers: Maximum concurrent containers (replaces concurrency_limit).
    """

    gpu: Optional[str] = None
    region: Optional[str] = None
    cloud: Optional[str] = None
    environment: Optional[str] = None
    cpu_count: Optional[int] = 8  # Default 8 CPU cores for blazing fast execution
    memory_mb: Optional[int] = 16384  # Default 16GB RAM for maximum speed
    timeout: int = 86400  # 24 hours (Modal's maximum)
    min_containers: Optional[int] = 1  # Keep 1 container warm for sequential execution
    max_containers: Optional[int] = 10  # Allow up to 10 concurrent containers


class ModalOrchestratorConfig(BaseOrchestratorConfig, ModalOrchestratorSettings):
    """Modal orchestrator config optimized for BLAZING FAST execution.
    
    Attributes:
        token: Modal API token for authentication. If not provided,
            falls back to Modal's default authentication (~/.modal.toml).
        workspace: Modal workspace name (optional).
        environment: Modal environment name (optional).
    """

    token: Optional[str] = None
    workspace: Optional[str] = None
    environment: Optional[str] = None

    @property
    def is_remote(self) -> bool:
        """Checks if this stack component is running remotely.

        Returns:
            True since Modal runs remotely.
        """
        return True

    @property
    def is_synchronous(self) -> bool:
        """Whether the orchestrator runs synchronous or not.

        Returns:
            True since the orchestrator waits for completion.
        """
        return True


class ModalOrchestratorFlavor(BaseOrchestratorFlavor):
    """Flavor for the Modal orchestrator."""

    @property
    def name(self) -> str:
        """Name of the orchestrator flavor.

        Returns:
            Name of the orchestrator flavor.
        """
        return "modal"

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
        return "https://public-flavor-logos.s3.eu-central-1.amazonaws.com/orchestrator/modal.png"

    @property
    def config_class(self) -> Type[BaseOrchestratorConfig]:
        """Config class for the Modal orchestrator flavor.

        Returns:
            The config class.
        """
        return ModalOrchestratorConfig

    @property
    def implementation_class(self) -> Type["ModalOrchestrator"]:
        """Implementation class for this flavor.

        Returns:
            Implementation class for this flavor.
        """
        return ModalOrchestrator