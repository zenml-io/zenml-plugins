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
from pydantic import SecretStr
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
    import sys

    print(f"🚀 Running step '{step_name}' in Modal")
    sys.stdout.flush()

    # Set the orchestrator run ID in the Modal environment
    os.environ["ZENML_MODAL_ORCHESTRATOR_RUN_ID"] = orchestrator_run_id

    try:
        from zenml.entrypoints.step_entrypoint_configuration import (
            StepEntrypointConfiguration,
        )

        print(f"🔧 Executing step '{step_name}' directly in process for maximum speed")
        sys.stdout.flush()

        # Create the entrypoint arguments
        args = StepEntrypointConfiguration.get_entrypoint_arguments(
            step_name=step_name, deployment_id=deployment_id
        )

        # Create the configuration and run the step
        config = StepEntrypointConfiguration(arguments=args)
        config.run()

        print(f"✅ Step {step_name} completed successfully")
        sys.stdout.flush()

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"💥 Error executing step {step_name}: {e}")
        print(f"📝 Full traceback:\n{error_details}")
        sys.stdout.flush()
        raise


def run_entire_pipeline_in_modal(
    step_names: list[str],
    deployment_id: str,
    orchestrator_run_id: str,
) -> None:
    """Execute ALL pipeline steps in a single Modal function for maximum speed."""
    import os
    import sys

    print(
        f"🚀 Running ENTIRE PIPELINE with {len(step_names)} steps in one Modal function!"
    )
    print(f"📋 Steps: {step_names}")
    sys.stdout.flush()

    # Set the orchestrator run ID in the Modal environment
    os.environ["ZENML_MODAL_ORCHESTRATOR_RUN_ID"] = orchestrator_run_id

    try:
        from zenml.entrypoints.step_entrypoint_configuration import (
            StepEntrypointConfiguration,
        )

        # Execute all steps sequentially in the same process for maximum speed
        for i, step_name in enumerate(step_names, 1):
            print(
                f"🏃‍♂️ [{i}/{len(step_names)}] Executing step '{step_name}' directly in process..."
            )
            sys.stdout.flush()

            # Create the entrypoint arguments
            args = StepEntrypointConfiguration.get_entrypoint_arguments(
                step_name=step_name, deployment_id=deployment_id
            )

            # Create the configuration and run the step
            config = StepEntrypointConfiguration(arguments=args)
            config.run()

            print(
                f"✅ [{i}/{len(step_names)}] Step '{step_name}' completed successfully"
            )
            sys.stdout.flush()

        print(
            f"🎉 ENTIRE PIPELINE COMPLETED! All {len(step_names)} steps finished in one function!"
        )
        sys.stdout.flush()

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"💥 Error executing pipeline: {e}")
        print(f"📝 Full traceback:\n{error_details}")
        sys.stdout.flush()
        raise


def run_entire_pipeline_with_pipeline_entrypoint(
    deployment_id: str,
    orchestrator_run_id: str,
) -> None:
    """Execute entire pipeline using PipelineEntrypointConfiguration for maximum efficiency."""
    import os
    import sys

    # Force unbuffered output for real-time log streaming to Modal
    import time

    print(
        "🚀 [MODAL] Starting ENTIRE PIPELINE using PipelineEntrypointConfiguration!",
        flush=True,
    )
    print(
        "⚡ [MODAL] This is the FASTEST mode - entire pipeline in same process!",
        flush=True,
    )
    print(f"📝 [MODAL] Deployment ID: {deployment_id}", flush=True)
    print(f"🆔 [MODAL] Orchestrator Run ID: {orchestrator_run_id}", flush=True)
    print(f"⏰ [MODAL] Start time: {time.strftime('%H:%M:%S')}", flush=True)

    # Set the orchestrator run ID in the Modal environment
    os.environ["ZENML_MODAL_ORCHESTRATOR_RUN_ID"] = orchestrator_run_id

    try:
        from zenml.entrypoints.pipeline_entrypoint_configuration import (
            PipelineEntrypointConfiguration,
        )

        print(
            "🔧 [MODAL] Initializing pipeline entrypoint configuration...", flush=True
        )

        # Create the entrypoint arguments
        args = PipelineEntrypointConfiguration.get_entrypoint_arguments(
            deployment_id=deployment_id
        )

        print("⚙️ [MODAL] Creating pipeline configuration...", flush=True)
        config = PipelineEntrypointConfiguration(arguments=args)

        print("🏃 [MODAL] Executing entire pipeline...", flush=True)
        config.run()

        print("🎉 [MODAL] ENTIRE PIPELINE COMPLETED SUCCESSFULLY!", flush=True)
        print(f"⏰ [MODAL] End time: {time.strftime('%H:%M:%S')}", flush=True)

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"💥 [MODAL] Error executing pipeline: {e}", flush=True)
        print(f"📝 [MODAL] Full traceback:\n{error_details}", flush=True)
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
    execution_mode: str = "single_function",
) -> modal.Function:
    """Get or deploy a persistent Modal app with warm containers.

    This function deploys a Modal app that stays alive with warm containers
    for maximum speed between pipeline runs.
    """
    # Use pipeline name + execution mode + 2-hour window for app reuse
    # This ensures apps get redeployed every 2 hours to refresh tokens
    mode_suffix = execution_mode.replace("_", "-")

    # Create a 2-hour timestamp window (rounds down to nearest 2-hour boundary)
    import time

    current_time = int(time.time())
    two_hour_window = current_time // (2 * 3600)  # 2 hours = 7200 seconds

    app_name = (
        f"zenml-{pipeline_name.replace('_', '-')}-{mode_suffix}-{two_hour_window}"
    )

    logger.info(f"🏗️  Getting/deploying persistent Modal app: {app_name}")

    # Create the app
    app = modal.App(app_name)

    # Ensure we have minimum containers for fast startup
    effective_min_containers = min_containers or 1
    effective_max_containers = max_containers or 10

    # Create the execution function based on execution mode
    if execution_mode == "pipeline_entrypoint":
        logger.info("🚀 Creating pipeline-entrypoint mode for MAXIMUM SPEED!")
        execution_func = run_entire_pipeline_with_pipeline_entrypoint
        function_name = "run_entire_pipeline_with_pipeline_entrypoint"
    elif execution_mode == "single_function":
        logger.info("⚡ Creating single-function mode for fast execution")
        execution_func = run_entire_pipeline_in_modal
        function_name = "run_entire_pipeline_in_modal"
    else:
        logger.info("🔧 Creating per-step mode for granular execution")
        execution_func = run_step_in_modal
        function_name = "run_step_in_modal"

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
    )(execution_func)

    # Try to lookup existing app in current 2-hour window, deploy if not found
    try:
        logger.info(f"🔍 Checking for Modal app in current 2-hour window: {app_name}")

        try:
            modal.App.lookup(app_name, environment_name=environment_name or "main")
            logger.info(
                f"♻️  Found existing app '{app_name}' with fresh tokens - reusing warm containers!"
            )

            # Try to get the function directly
            try:
                existing_function = modal.Function.from_name(
                    app_name,
                    function_name,
                    environment_name=environment_name or "main",
                )
                logger.info("✅ Successfully retrieved function from existing app!")
                return existing_function
            except Exception as func_error:
                logger.warning(
                    f"⚠️  Function lookup failed: {func_error}, redeploying..."
                )
                # Fall through to deployment

        except Exception as lookup_error:
            # App not found or other lookup error - deploy fresh app
            logger.info(
                "🆕 No app found for current 2-hour window, deploying fresh app..."
            )

        # Deploy the app
        app.deploy(name=app_name, environment_name=environment_name or "main")
        logger.info(
            f"✅ App '{app_name}' deployed with fresh tokens and {effective_min_containers} warm containers"
        )

    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        raise

    logger.info(
        f"🔥 Modal app configured for SPEED with min_containers={effective_min_containers}, max_containers={effective_max_containers}"
    )
    logger.info(
        f"💡 This means {effective_min_containers} containers will stay warm for faster execution!"
    )

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
            os.environ["MODAL_TOKEN_ID"] = self.config.token.get_secret_value()
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
    ) -> Any:
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
            modal.Image.from_registry(image_name, secret=registry_secret)
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
            placeholder_run: An optional placeholder run for the deployment (unused).

        Raises:
            RuntimeError: If a step fails.
        """
        _ = placeholder_run  # Mark as intentionally unused
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
            cpu_count=cpu_count or 8,  # Default to 8 CPU cores for speed
            memory_mb=memory_mb or 16384,  # Default to 16GB RAM for speed
            cloud=settings.cloud or self.config.cloud,
            region=settings.region or self.config.region,
            timeout=settings.timeout or self.config.timeout,
            min_containers=settings.min_containers
            or self.config.min_containers
            or 1,  # Keep 1 warm container for sequential execution
            max_containers=settings.max_containers
            or self.config.max_containers
            or 10,  # Scale to 10 containers
            environment_name=settings.environment
            or self.config.environment,  # Use environment from config/settings
            execution_mode=settings.execution_mode
            or self.config.execution_mode,  # Use execution mode from settings
        )

        logger.info("⚡ Executing with DEPLOYED Modal app and warm containers...")

        # Execute based on execution mode with improved Modal Function API usage
        execution_mode = settings.execution_mode or self.config.execution_mode
        sync_execution = (
            settings.synchronous
            if hasattr(settings, "synchronous")
            else self.config.synchronous
        )
        enable_log_streaming = (
            settings.enable_log_streaming
            if hasattr(settings, "enable_log_streaming")
            else self.config.enable_log_streaming
        )

        def execute_modal_function(func_args: tuple, description: str) -> None:
            """Execute Modal function with proper sync/async and log streaming control."""
            logger.info(f"🚀 {description}")

            if sync_execution:
                if enable_log_streaming:
                    logger.info(
                        "📡 Using .remote() for synchronous execution with log streaming"
                    )
                    # .remote() waits for completion and should stream logs
                    result = execute_step.remote(*func_args)
                    logger.info(f"✅ {description} completed successfully!")
                    return result
                else:
                    logger.info(
                        "⚡ Using .spawn() + .get() for synchronous execution without log streaming"
                    )
                    # .spawn() + .get() for sync execution without streaming
                    function_call = execute_step.spawn(*func_args)
                    result = function_call.get()  # Wait for completion
                    logger.info(f"✅ {description} completed successfully!")
                    return result
            else:
                logger.info(
                    "🔥 Using .spawn() for asynchronous fire-and-forget execution"
                )
                # .spawn() for fire-and-forget (async)
                function_call = execute_step.spawn(*func_args)
                logger.info(
                    f"🚀 {description} started asynchronously (not waiting for completion)"
                )
                return function_call

        if execution_mode == "pipeline_entrypoint":
            try:
                execute_modal_function(
                    (deployment.id, orchestrator_run_id),
                    "Pipeline-entrypoint mode execution (MAXIMUM SPEED)",
                )
            except Exception as e:
                logger.error(f"❌ Pipeline failed: {e}")
                logger.error("💡 Check Modal dashboard for detailed logs")
                raise

        elif execution_mode == "single_function":
            try:
                execute_modal_function(
                    (step_names, deployment.id, orchestrator_run_id),
                    "Single-function mode execution (all steps in one function)",
                )
            except Exception as e:
                logger.error(f"❌ Pipeline failed: {e}")
                logger.error("💡 Check Modal dashboard for detailed logs")
                raise

        else:  # per_step mode
            logger.info("🔧 Using per-step mode for granular execution...")
            # Execute steps individually
            for step_name in step_names:
                try:
                    execute_modal_function(
                        (step_name, deployment.id, orchestrator_run_id),
                        f"Step '{step_name}' execution",
                    )
                except Exception as e:
                    logger.error(f"❌ Step '{step_name}' failed: {e}")
                    logger.error("💡 Check Modal dashboard for detailed logs")
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
        execution_mode: Execution mode - "pipeline_entrypoint" (fastest), "single_function", or "per_step".
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
    execution_mode: str = "single_function"  # Default to fastest mode
    synchronous: bool = False  # Wait for completion (True) or fire-and-forget (False)
    enable_log_streaming: bool = False  # Enable real-time log streaming


class ModalOrchestratorConfig(BaseOrchestratorConfig, ModalOrchestratorSettings):
    """Modal orchestrator config optimized for BLAZING FAST execution.

    Attributes:
        token: Modal API token for authentication. If not provided,
            falls back to Modal's default authentication (~/.modal.toml).
        workspace: Modal workspace name (optional).
        environment: Modal environment name (optional).
    """

    token: Optional[SecretStr] = None
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
