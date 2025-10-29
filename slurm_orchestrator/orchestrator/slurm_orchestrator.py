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
"""Implementation of the SLURM orchestrator for ZenML."""

import copy
import os
import re
import shlex
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast
from uuid import uuid4

from zenml.config.base_settings import BaseSettings
from zenml.config.global_config import GlobalConfiguration
from zenml.constants import ENV_ZENML_LOCAL_STORES_PATH
from zenml.entrypoints import StepEntrypointConfiguration
from zenml.enums import ExecutionMode, StackComponentType
from zenml.logger import get_logger
from zenml.orchestrators import (
    BaseOrchestratorConfig,
    BaseOrchestratorFlavor,
    ContainerizedOrchestrator,
    SubmissionResult,
)
from zenml.stack import Stack, StackValidator
from zenml.utils import string_utils

if TYPE_CHECKING:
    from zenml.models import PipelineRunResponse, PipelineSnapshotResponse

logger = get_logger(__name__)

ENV_ZENML_SLURM_ORCHESTRATOR_RUN_ID = "ZENML_SLURM_ORCHESTRATOR_RUN_ID"


class SlurmOrchestratorSettings(BaseSettings):
    """SLURM orchestrator settings.

    These settings can be customized per-stack or per-step.

    Attributes:
        partition: SLURM partition to submit jobs to.
        account: SLURM account/project name (optional).
        qos: Quality of Service level (optional).
        job_name_prefix: Prefix for SLURM job names.
        output_dir: Directory to store SLURM output files.
        synchronous: Whether to wait for job completion.
        sbatch_args: Dictionary of additional sbatch arguments to pass.
        docker_run_args: Dictionary of additional docker run arguments.
        poll_interval: Seconds to wait between job status checks.
    """

    partition: str = "default"
    account: Optional[str] = None
    qos: Optional[str] = None
    job_name_prefix: str = "zenml"
    output_dir: str = "/home/zenml_slurm_logs"
    synchronous: bool = True
    sbatch_args: Dict[str, Any] = {}
    docker_run_args: Dict[str, Any] = {}
    poll_interval: int = 5
    nodelist: Optional[str] = None  # Specific node(s) to use, e.g., "hpcslurm-computenodeset-0"


class SlurmOrchestratorConfig(BaseOrchestratorConfig, SlurmOrchestratorSettings):
    """SLURM orchestrator configuration.

    Extends both BaseOrchestratorConfig and SlurmOrchestratorSettings
    to provide a unified configuration object for registration.
    """

    @property
    def is_local(self) -> bool:
        """Checks if this stack component is running locally.

        Returns:
            False, as SLURM orchestrator runs on remote cluster.
        """
        return False


class SlurmOrchestrator(ContainerizedOrchestrator):
    """Orchestrator responsible for running pipelines on SLURM clusters.

    This orchestrator submits pipeline steps as SLURM jobs via sbatch,
    with support for Docker container execution, resource specifications,
    and automatic job dependency management.
    """

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the SLURM orchestrator.

        Returns:
            The settings class.
        """
        return SlurmOrchestratorSettings

    @property
    def config(self) -> "SlurmOrchestratorConfig":
        """Returns the SLURM orchestrator config.

        Returns:
            The SLURM orchestrator configuration.
        """
        return cast(SlurmOrchestratorConfig, self._config)

    @property
    def validator(self) -> Optional[StackValidator]:
        """Ensures there is an image builder in the stack.

        Returns:
            A `StackValidator` instance.
        """
        return StackValidator(
            required_components={StackComponentType.IMAGE_BUILDER}
        )

    def _validate_sbatch_available(self) -> None:
        """Validate that sbatch is available on the system.

        Raises:
            RuntimeError: If sbatch is not found or not executable.
        """
        try:
            result = subprocess.run(
                ["sbatch", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("SLURM available: %s", result.stdout.strip())
        except FileNotFoundError:
            raise RuntimeError(
                "sbatch command not found. Ensure you're running from a SLURM "
                "cluster login node and SLURM is properly installed."
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to verify sbatch availability: {e.stderr}"
            )

    def get_orchestrator_run_id(self) -> str:
        """Returns the active orchestrator run id.

        The run ID is stored in an environment variable that is set
        when steps are executed on SLURM compute nodes.

        Raises:
            RuntimeError: If the environment variable specifying the run id
                is not set.

        Returns:
            The orchestrator run id.
        """
        try:
            return os.environ[ENV_ZENML_SLURM_ORCHESTRATOR_RUN_ID]
        except KeyError:
            raise RuntimeError(
                "Unable to read run id from environment variable "
                f"{ENV_ZENML_SLURM_ORCHESTRATOR_RUN_ID}."
            )

    def _generate_slurm_script(
        self,
        step_name: str,
        image: str,
        entrypoint: str,
        arguments: str,
        environment: Dict[str, str],
        orchestrator_run_id: str,
        settings: "SlurmOrchestratorSettings",
        step_resources: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generates a SLURM job submission script.

        Args:
            step_name: Name of the step being executed.
            image: Docker image to run.
            entrypoint: Entrypoint command for the step.
            arguments: Arguments to pass to the entrypoint.
            environment: Environment variables to set.
            orchestrator_run_id: ID of the orchestrator run.
            settings: SLURM-specific settings for this step.
            step_resources: Optional resource specifications for the step.

        Returns:
            The SLURM job script as a string.
        """
        # Start with SLURM shebang and basic setup
        script = "#!/bin/bash\n"
        script += f"#SBATCH --job-name={settings.job_name_prefix}_{step_name}\n"
        script += f"#SBATCH --partition={settings.partition}\n"

        if settings.account:
            script += f"#SBATCH --account={settings.account}\n"

        if settings.qos:
            script += f"#SBATCH --qos={settings.qos}\n"

        if settings.nodelist:
            script += f"#SBATCH --nodelist={settings.nodelist}\n"

        # Map resource settings to SLURM directives
        if step_resources:
            if step_resources.get("cpu_count"):
                script += f"#SBATCH --cpus-per-task={step_resources['cpu_count']}\n"
            if step_resources.get("memory"):
                script += f"#SBATCH --mem={step_resources['memory']}\n"
            if step_resources.get("gpu"):
                script += f"#SBATCH --gpus={step_resources['gpu']}\n"
            if step_resources.get("time"):
                script += f"#SBATCH --time={step_resources['time']}\n"

        # Add any additional sbatch arguments from settings
        for key, value in settings.sbatch_args.items():
            if isinstance(value, bool):
                if value:
                    script += f"#SBATCH --{key}\n"
            else:
                script += f"#SBATCH --{key}={value}\n"

        # Add output/error file handling
        if settings.output_dir:
            os.makedirs(settings.output_dir, exist_ok=True)
            script += f"#SBATCH --output={settings.output_dir}/{settings.job_name_prefix}_{step_name}_%j.out\n"
            script += f"#SBATCH --error={settings.output_dir}/{settings.job_name_prefix}_{step_name}_%j.err\n"

        script += "\n"

        # Set environment variables with proper shell escaping
        script += "# Set environment variables\n"
        environment[ENV_ZENML_SLURM_ORCHESTRATOR_RUN_ID] = orchestrator_run_id
        environment[ENV_ZENML_LOCAL_STORES_PATH] = GlobalConfiguration().local_stores_path

        for key, value in environment.items():
            # Use shlex.quote for proper shell escaping
            script += f"export {key}={shlex.quote(value)}\n"

        script += "\n"

        # Get paths for volume mounting
        local_stores_path = GlobalConfiguration().local_stores_path
        current_dir = os.getcwd()

        # Add Docker readiness check
        script += "# Wait for Docker to be available\n"
        script += "echo 'Checking Docker availability...'\n"
        script += "MAX_RETRIES=30\n"
        script += "RETRY_COUNT=0\n"
        script += "while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do\n"
        script += "  if command -v docker &> /dev/null && docker ps &> /dev/null; then\n"
        script += "    echo 'Docker is ready'\n"
        script += "    break\n"
        script += "  fi\n"
        script += "  RETRY_COUNT=$((RETRY_COUNT + 1))\n"
        script += "  echo \"Docker not ready yet (attempt $RETRY_COUNT/$MAX_RETRIES), waiting...\"\n"
        script += "  sleep 2\n"
        script += "done\n"
        script += "if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then\n"
        script += "  echo 'ERROR: Docker failed to become available after 60 seconds'\n"
        script += "  exit 127\n"
        script += "fi\n"
        script += "\n"

        # Docker run command with log streaming
        script += "# Run step in Docker with log streaming to shared storage\n"
        shared_log_path = f"{settings.output_dir}/{settings.job_name_prefix}_{step_name}_shared.log"
        script += f"echo 'Starting step {step_name}' | tee {shared_log_path}\n"
        script += "(\n"
        script += "docker run --rm \\\n"

        # Volume mounts - mount both artifact store and code directory
        script += f"  -v {local_stores_path}:{local_stores_path} \\\n"
        script += f"  -v {current_dir}:{current_dir} \\\n"
        script += f"  -w {current_dir} \\\n"

        # Custom docker run arguments from settings
        for key, value in settings.docker_run_args.items():
            if isinstance(value, bool):
                if value:
                    script += f"  --{key} \\\n"
            else:
                script += f"  --{key}={shlex.quote(str(value))} \\\n"

        # Environment variables
        script += "  "
        for key in environment:
            script += f"-e {key} \\\n  "

        # Image and command
        script += f"  {image}"

        # Handle entrypoint and arguments (they may be lists or strings)
        if isinstance(entrypoint, list):
            entrypoint_str = " ".join(entrypoint)
        else:
            entrypoint_str = entrypoint

        if isinstance(arguments, list):
            arguments_str = " ".join(arguments)
        else:
            arguments_str = arguments

        script += f" \\\n  {entrypoint_str}"
        if arguments_str:
            script += f" {arguments_str}"
        script += "\n"

        # Close the subshell and pipe all output to both SLURM logs and shared storage
        script += f") 2>&1 | tee -a {shared_log_path}\n"
        script += f"EXIT_CODE=${{PIPESTATUS[0]}}\n"
        script += f"echo 'Step {step_name} completed with exit code: $EXIT_CODE' | tee -a {shared_log_path}\n"
        script += "exit $EXIT_CODE\n"

        logger.debug("Generated SLURM script for step %s:\n%s", step_name, script)
        return script

    def _extract_job_id(self, sbatch_output: str) -> str:
        """Extract job ID from sbatch output.

        Args:
            sbatch_output: Output from sbatch command.

        Returns:
            The extracted job ID.

        Raises:
            RuntimeError: If job ID cannot be extracted.
        """
        # SLURM sbatch output format: "Submitted batch job 12345"
        match = re.search(r"Submitted batch job (\d+)", sbatch_output)
        if match:
            job_id = match.group(1)
            if job_id.isdigit():
                return job_id

        raise RuntimeError(
            f"Could not parse job ID from sbatch output. Got: {sbatch_output}"
        )

    def _get_job_exit_code(self, job_id: str) -> Optional[int]:
        """Get the exit code of a completed SLURM job.

        Args:
            job_id: The SLURM job ID.

        Returns:
            The exit code if available, None if job not found or still running.
        """
        try:
            result = subprocess.run(
                ["sacct", "-j", job_id, "--format=ExitCode", "--parsable2"],
                capture_output=True,
                text=True,
                check=True,
            )

            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                # Skip header, get first data line
                exit_code_str = lines[1].split(":")[0]  # Format: "0:0" (job:step)
                try:
                    return int(exit_code_str)
                except ValueError:
                    return None
        except subprocess.CalledProcessError:
            return None

    def _cancel_submitted_jobs(self, submitted_jobs: Dict[str, str]) -> None:
        """Cancel all submitted SLURM jobs.

        Args:
            submitted_jobs: Dictionary mapping step names to job IDs.
        """
        logger.warning("Cancelling all submitted SLURM jobs...")
        for step_name, job_id in submitted_jobs.items():
            try:
                subprocess.run(
                    ["scancel", job_id],
                    capture_output=True,
                    check=False,
                )
                logger.info("Cancelled SLURM job %s for step %s", job_id, step_name)
            except Exception as e:
                logger.warning(
                    "Failed to cancel SLURM job %s: %s", job_id, str(e)
                )

    def submit_pipeline(
        self,
        snapshot: "PipelineSnapshotResponse",
        stack: "Stack",
        base_environment: Dict[str, str],
        step_environments: Dict[str, Dict[str, str]],
        placeholder_run: Optional["PipelineRunResponse"] = None,
    ) -> Optional[SubmissionResult]:
        """Submits a pipeline to the SLURM orchestrator.

        Args:
            snapshot: The pipeline snapshot to submit.
            stack: The stack the pipeline will run on.
            base_environment: Base environment shared by all steps.
            step_environments: Environment variables to set when executing
                specific steps.
            placeholder_run: An optional placeholder run for the snapshot.

        Returns:
            Optional submission result.

        Raises:
            RuntimeError: If a step fails or submission fails.
        """
        # Validate SLURM availability upfront
        self._validate_sbatch_available()

        if snapshot.schedule:
            logger.warning(
                "SLURM Orchestrator currently does not support the "
                "use of schedules. The `schedule` will be ignored "
                "and the pipeline will be run immediately."
            )

        # Generate unique orchestrator run ID
        orchestrator_run_id = str(uuid4())
        start_time = time.time()
        execution_mode = snapshot.pipeline_configuration.execution_mode

        # Track submitted job IDs for dependency management
        submitted_jobs: Dict[str, str] = {}
        failed_steps: List[str] = []
        skipped_steps: List[str] = []

        # Get default settings from the orchestrator's config
        # The config contains the orchestrator-level settings (registered with zenml orchestrator register)
        default_settings = self.config

        # Create output directory if configured
        if default_settings.output_dir:
            os.makedirs(default_settings.output_dir, exist_ok=True)

        try:
            # Submit each step as a SLURM job
            for step_name, step in snapshot.step_configurations.items():
                # Handle execution modes
                if (
                    execution_mode == ExecutionMode.STOP_ON_FAILURE
                    and failed_steps
                ):
                    logger.warning(
                        "Skipping step %s due to the failed step(s): %s",
                        step_name,
                        ", ".join(failed_steps),
                    )
                    skipped_steps.append(step_name)
                    continue

                if failed_upstream_steps := [
                    fs for fs in failed_steps if fs in step.spec.upstream_steps
                ]:
                    logger.warning(
                        "Skipping step %s due to failure in upstream step(s): %s",
                        step_name,
                        ", ".join(failed_upstream_steps),
                    )
                    skipped_steps.append(step_name)
                    continue

                if skipped_upstream_steps := [
                    fs for fs in skipped_steps if fs in step.spec.upstream_steps
                ]:
                    logger.warning(
                        "Skipping step %s due to the skipped upstream step(s): %s",
                        step_name,
                        ", ".join(skipped_upstream_steps),
                    )
                    skipped_steps.append(step_name)
                    continue

                # Extract resource specifications
                step_resources = {}
                if self.requires_resources_in_orchestration_environment(step):
                    resources = step.config.resource_settings
                    logger.info(
                        "Step %s has resource requirements: %s",
                        step_name,
                        resources,
                    )
                    # Map resource settings to SLURM format
                    if resources.cpu_count:
                        step_resources["cpu_count"] = resources.cpu_count
                    if resources.memory:
                        step_resources["memory"] = resources.memory
                    if resources.gpu:
                        step_resources["gpu"] = resources.gpu
                    if resources.requests:
                        # requests is a dict, extract time if present
                        step_resources["time"] = resources.requests.get("time", "01:00:00")

                # Get step configuration
                step_environment = copy.deepcopy(base_environment)
                step_environment.update(step_environments[step_name])

                image = self.get_image(snapshot=snapshot, step_name=step_name)
                entrypoint = StepEntrypointConfiguration.get_entrypoint_command()
                arguments = StepEntrypointConfiguration.get_entrypoint_arguments(
                    step_name=step_name, snapshot_id=snapshot.id
                )

                # Get settings for this step (allows per-step customization)
                settings = cast(
                    SlurmOrchestratorSettings,
                    self.get_settings(step),
                )

                # Generate SLURM script
                script = self._generate_slurm_script(
                    step_name=step_name,
                    image=image,
                    entrypoint=entrypoint,
                    arguments=arguments,
                    environment=step_environment,
                    orchestrator_run_id=orchestrator_run_id,
                    settings=settings,
                    step_resources=step_resources,
                )

                # Save script to file with unique identifier
                script_dir = settings.output_dir or "/tmp"
                os.makedirs(script_dir, exist_ok=True)
                script_path = os.path.join(
                    script_dir,
                    f"zenml_slurm_{orchestrator_run_id}_{step_name}.sh",
                )
                with open(script_path, "w") as f:
                    f.write(script)
                os.chmod(script_path, 0o755)

                logger.info("Generated SLURM script for step %s: %s", step_name, script_path)

                # Submit job to SLURM
                try:
                    sbatch_cmd = ["sbatch"]

                    # Add job dependency if there are upstream steps
                    if step.spec.upstream_steps:
                        upstream_job_ids = [
                            submitted_jobs[us] for us in step.spec.upstream_steps
                            if us in submitted_jobs
                        ]
                        if upstream_job_ids:
                            # SLURM dependency format: afterok:job1,job2 (comma-separated)
                            dependency_str = ",".join(upstream_job_ids)
                            sbatch_cmd.extend(["--dependency", f"afterok:{dependency_str}"])

                    sbatch_cmd.append(script_path)

                    logger.info("Submitting SLURM job with command: %s", " ".join(sbatch_cmd))
                    result = subprocess.run(
                        sbatch_cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Extract job ID from sbatch output with validation
                    job_id = self._extract_job_id(result.stdout)
                    submitted_jobs[step_name] = job_id
                    logger.info("Step %s submitted with SLURM job ID: %s", step_name, job_id)

                except subprocess.CalledProcessError as e:
                    failed_steps.append(step_name)
                    error_msg = f"Failed to submit step {step_name}: {e.stderr}"
                    logger.error(error_msg)

                    if execution_mode == ExecutionMode.FAIL_FAST:
                        self._cancel_submitted_jobs(submitted_jobs)
                        raise RuntimeError(error_msg)

            # If synchronous, wait for job completion and check exit codes
            if default_settings.synchronous:
                def _wait_for_completion() -> None:
                    """Wait for all submitted jobs to complete and check exit codes."""
                    logger.info("Waiting for SLURM jobs to complete...")

                    failed_jobs = {}
                    while submitted_jobs:
                        try:
                            # Check job status
                            squeue_cmd = ["squeue", "-j", ",".join(submitted_jobs.values())]
                            result = subprocess.run(
                                squeue_cmd,
                                capture_output=True,
                                text=True,
                            )

                            # If no output (except header), all jobs are done
                            if len(result.stdout.strip().split("\n")) <= 1:
                                logger.info("All SLURM jobs completed")

                                # Check exit codes of completed jobs
                                for step_name, job_id in list(submitted_jobs.items()):
                                    exit_code = self._get_job_exit_code(job_id)
                                    if exit_code is not None and exit_code != 0:
                                        failed_jobs[step_name] = (job_id, exit_code)
                                        logger.error(
                                            "Step %s (job %s) failed with exit code %d",
                                            step_name,
                                            job_id,
                                            exit_code,
                                        )
                                    submitted_jobs.pop(step_name, None)

                                break

                            time.sleep(default_settings.poll_interval)
                        except Exception as e:
                            logger.warning("Error checking job status: %s", e)
                            time.sleep(default_settings.poll_interval)

                    # Raise error if any jobs failed
                    if failed_jobs:
                        error_msg = "The following steps failed:\n"
                        for step_name, (job_id, exit_code) in failed_jobs.items():
                            error_msg += f"  - {step_name} (job {job_id}, exit code {exit_code})\n"
                        raise RuntimeError(error_msg)

                return SubmissionResult(wait_for_completion=_wait_for_completion)

        except Exception:
            # Clean up any submitted jobs on error
            if submitted_jobs:
                self._cancel_submitted_jobs(submitted_jobs)
            raise

        run_duration = time.time() - start_time
        logger.info(
            "Pipeline submitted to SLURM in `%s`.",
            string_utils.get_human_readable_time(run_duration),
        )

        if failed_steps and execution_mode == ExecutionMode.FAIL_FAST:
            raise RuntimeError(
                "Pipeline submission failed due to failure in step(s): "
                f"{', '.join(failed_steps)}"
            )

        return None

    @property
    def supported_execution_modes(self) -> List[ExecutionMode]:
        """Supported execution modes for this orchestrator.

        Returns:
            Supported execution modes for this orchestrator.
        """
        return [
            ExecutionMode.FAIL_FAST,
            ExecutionMode.STOP_ON_FAILURE,
            ExecutionMode.CONTINUE_ON_FAILURE,
        ]


class SlurmOrchestratorFlavor(BaseOrchestratorFlavor):
    """Flavor for the SLURM orchestrator."""

    @property
    def name(self) -> str:
        """Name of the orchestrator flavor.

        Returns:
            Name of the orchestrator flavor.
        """
        return "slurm"

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
        return "https://public-flavor-logos.s3.eu-central-1.amazonaws.com/orchestrator/kubernetes.png"

    @property
    def config_class(self) -> Type[BaseOrchestratorConfig]:
        """Config class for the base orchestrator flavor.

        Returns:
            The config class.
        """
        return SlurmOrchestratorConfig

    @property
    def implementation_class(self) -> Type["SlurmOrchestrator"]:
        """Implementation class for this flavor.

        Returns:
            Implementation class for this flavor.
        """
        return SlurmOrchestrator
