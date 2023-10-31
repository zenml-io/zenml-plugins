#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
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
"""Implementation of the Seldon Model Deployer."""

import json
import os
import sagemaker
import boto3
import re
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Type, cast
from uuid import UUID

from zenml.analytics.enums import AnalyticsEvent
from zenml.analytics.utils import track_handler
from zenml.client import Client
from zenml.config.build_configuration import BuildConfiguration
from zenml.enums import StackComponentType
from zenml.logger import get_logger
from zenml.model_deployers import BaseModelDeployer, BaseModelDeployerFlavor
from zenml.secret.base_secret import BaseSecretSchema
from zenml.services.service import BaseService, ServiceConfig
from zenml.stack import StackValidator


from zenml.integrations.seldon.constants import (
    SELDON_CUSTOM_DEPLOYMENT,
    SELDON_DOCKER_IMAGE_KEY,
)
from zenml.integrations.seldon.flavors.seldon_model_deployer_flavor import (
    SeldonModelDeployerConfig,
    SeldonModelDeployerFlavor,
)
from zenml.integrations.seldon.secret_schemas.secret_schemas import (
    SeldonAzureSecretSchema,
    SeldonGSSecretSchema,
    SeldonS3SecretSchema,
)
from zenml.integrations.seldon.seldon_client import SeldonClient
from zenml.integrations.seldon.services.seldon_deployment import (
    SeldonDeploymentConfig,
    SeldonDeploymentService,
)

from hf_sagemaker_model_deployer_flavor import (
    HFSagemakerModelDeployerFlavor,
    HFSagemakerModelDeployerConfig,
    HFSagemakerModelDeployerSettings,
)
from hf_sagemaker_deployment_service import HFSagemakerDeploymentService

if TYPE_CHECKING:
    from zenml.models.pipeline_deployment_models import (
        PipelineDeploymentBaseModel,
    )
    from zenml.config.base_settings import BaseSettings

logger = get_logger(__name__)


DEFAULT_HUGGINGFACE_SAGEMAKER_DEPLOYMENT_START_STOP_TIMEOUT = 300
ENV_AWS_PROFILE = "AWS_PROFILE"


class HFSagemakerModelDeployer(BaseModelDeployer):
    """Huggingface Sagemaker model deployer stack component implementation."""

    NAME: ClassVar[str] = "Huggingface Sagemaker"
    FLAVOR: ClassVar[Type[BaseModelDeployerFlavor]] = HFSagemakerModelDeployerFlavor

    @property
    def config(self) -> HFSagemakerModelDeployerConfig:
        """Returns the `HFSagemakerModelDeployerConfig` config.

        Returns:
            The configuration.
        """
        return cast(HFSagemakerModelDeployerConfig, self._config)

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the Skypilot orchestrator.

        Returns:
            The settings class.
        """
        return HFSagemakerModelDeployerSettings

    def prepare_environment_variable(self, set: bool = True) -> None:
        """Set up Environment variables that are required for the orchestrator.

        Args:
            set: Whether to set the environment variables or not.

        Raises:
            ValueError: If no service connector is found.
        """
        connector = self.get_connector()
        if connector is None:
            raise ValueError(
                "No service connector found. Please make sure to set up a connector "
                "that is compatible with this orchestrator."
            )
        if set:
            # The AWS connector creates a local configuration profile with the name computed from
            # the first 8 digits of its UUID.
            aws_profile = f"zenml-{str(connector.id)[:8]}"
            os.environ[ENV_AWS_PROFILE] = aws_profile
        else:
            os.environ.pop(ENV_AWS_PROFILE, None)

    def get_sagemaker_session(
        self, settings: HFSagemakerModelDeployerSettings
    ) -> sagemaker.Session:
        """Returns sagemaker session from connector"""
        self.prepare_environment_variable(set=True)
        session = sagemaker.Session(boto3.Session(**settings.sagemaker_session_args))
        return session

    @staticmethod
    def get_model_server_info(  # type: ignore[override]
        service_instance: "HFSagemakerDeploymentService",
    ) -> Dict[str, Optional[str]]:
        """Return implementation specific information that might be relevant to the user.

        Args:
            service_instance: Instance of a HFSagemakerDeploymentService

        Returns:
            Model server information.
        """
        return {
            "ENDPOINT_NAME": service_instance.endpoint_name,
        }

    @property
    def kubernetes_secret_name(self) -> str:
        """Get the Kubernetes secret name associated with this model deployer.

        If a pre-existing Kubernetes secret is configured for this model
        deployer, that name is returned to be used by all Seldon Core
        deployments associated with this model deployer.

        Otherwise, a Kubernetes secret name is generated based on the ID of
        the active artifact store. The reason for this is that the same model
        deployer may be used to deploy models in combination with different
        artifact stores at the same time, and each artifact store may require
        different credentials to be accessed.

        Returns:
            The name of a Kubernetes secret to be used with Seldon Core
            deployments.
        """
        if self.config.kubernetes_secret_name:
            return self.config.kubernetes_secret_name

        artifact_store = Client().active_stack.artifact_store

        return (
            re.sub(
                r"[^0-9a-zA-Z-]+",
                "-",
                f"zenml-seldon-core-{artifact_store.id}",
            )
            .strip("-")
            .lower()
        )

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
            if step.config.extra.get(SELDON_CUSTOM_DEPLOYMENT, False) is True:
                build = BuildConfiguration(
                    key=SELDON_DOCKER_IMAGE_KEY,
                    settings=step.config.docker_settings,
                    step_name=step_name,
                )
                builds.append(build)

        return builds

    def _create_or_update_kubernetes_secret(self) -> Optional[str]:
        """Create or update the Kubernetes secret used to access the artifact store.

        Uses the information stored in the ZenML secret configured for the model deployer.

        Returns:
            The name of the Kubernetes secret that was created or updated, or
            None if no secret was configured.

        Raises:
            RuntimeError: if the secret cannot be created or updated.
        """
        # if a Kubernetes secret was explicitly configured in the model
        # deployer, use that instead of creating a new one
        if self.config.kubernetes_secret_name:
            logger.warning(
                "Your Seldon Core model deployer is configured to use a "
                "pre-existing Kubernetes secret that holds credentials needed "
                "to access the artifact store. The authentication method is "
                "deprecated and will be removed in a future release. Please "
                "remove this attribute by running `zenml model-deployer "
                f"remove-attribute {self.name} --kubernetes_secret_name` and "
                "configure credentials for the artifact store stack component "
                "instead. The Seldon Core model deployer will use those "
                "credentials to authenticate to the artifact store "
                "automatically."
            )

            return self.config.kubernetes_secret_name

        # if a ZenML secret reference was configured in the model deployer,
        # create a Kubernetes secret from that
        if self.config.secret:
            logger.warning(
                "Your Seldon Core model deployer is configured to use a "
                "ZenML secret that holds credentials needed to access the "
                "artifact store. The recommended authentication method is to "
                "configure credentials for the artifact store stack component "
                "instead. The Seldon Core model deployer will use those "
                "credentials to authenticate to the artifact store "
                "automatically."
            )

            try:
                zenml_secret = Client().get_secret_by_name_and_scope(
                    name=self.config.secret,
                )
            except KeyError as e:
                raise RuntimeError(
                    f"The ZenML secret '{self.config.secret}' specified in the "
                    f"Seldon Core Model Deployer configuration was not found "
                    f"in the secrets store: {e}."
                )

            self.seldon_client.create_or_update_secret(
                self.kubernetes_secret_name, zenml_secret.secret_values
            )

        else:
            # if no ZenML secret was configured, try to convert the credentials
            # configured for the artifact store, if any are included, into
            # the format expected by Seldon Core
            converted_secret = self._convert_artifact_store_secret()

            self.seldon_client.create_or_update_secret(
                self.kubernetes_secret_name, converted_secret.content
            )

        return self.kubernetes_secret_name

    def _convert_artifact_store_secret(self) -> BaseSecretSchema:
        """Convert the credentials configured for the artifact store into a ZenML secret.

        Returns:
            The ZenML secret.

        Raises:
            RuntimeError: if the credentials cannot be converted.
        """
        artifact_store = Client().active_stack.artifact_store

        zenml_secret: BaseSecretSchema

        if artifact_store.flavor == "s3":
            from zenml.integrations.s3.artifact_stores import S3ArtifactStore

            assert isinstance(artifact_store, S3ArtifactStore)

            (
                aws_access_key_id,
                aws_secret_access_key,
                aws_session_token,
            ) = artifact_store.get_credentials()

            if aws_access_key_id and aws_secret_access_key:
                # Convert the credentials into the format expected by Seldon
                # Core
                zenml_secret = SeldonS3SecretSchema(
                    name="",
                    rclone_config_s3_access_key_id=aws_access_key_id,
                    rclone_config_s3_secret_access_key=aws_secret_access_key,
                    rclone_config_s3_session_token=aws_session_token,
                )
                if (
                    artifact_store.config.client_kwargs
                    and "endpoint_url" in artifact_store.config.client_kwargs
                ):
                    zenml_secret.rclone_config_s3_endpoint = (
                        artifact_store.config.client_kwargs["endpoint_url"]
                    )
                    # Assume minio is the provider if endpoint is set
                    zenml_secret.rclone_config_s3_provider = "Minio"

                return zenml_secret

            logger.warning(
                "No credentials are configured for the active S3 artifact "
                "store. The Seldon Core model deployer will assume an "
                "implicit form of authentication is available in the "
                "target Kubernetes cluster, but the served model may not "
                "be able to access the model artifacts."
            )

            # Assume implicit in-cluster IAM authentication
            return SeldonS3SecretSchema(name="", rclone_config_s3_env_auth=True)

        elif artifact_store.flavor == "gcp":
            from zenml.integrations.gcp.artifact_stores import GCPArtifactStore

            assert isinstance(artifact_store, GCPArtifactStore)

            gcp_credentials = artifact_store.get_credentials()

            if gcp_credentials:
                # Convert the credentials into the format expected by Seldon
                # Core
                if isinstance(gcp_credentials, dict):
                    if gcp_credentials.get("type") == "service_account":
                        return SeldonGSSecretSchema(
                            name="",
                            rclone_config_gs_service_account_credentials=json.dumps(
                                gcp_credentials
                            ),
                        )
                    elif gcp_credentials.get("type") == "authorized_user":
                        return SeldonGSSecretSchema(
                            name="",
                            rclone_config_gs_client_id=gcp_credentials.get("client_id"),
                            rclone_config_gs_client_secret=gcp_credentials.get(
                                "client_secret"
                            ),
                            rclone_config_gs_token=json.dumps(
                                dict(refresh_token=gcp_credentials.get("refresh_token"))
                            ),
                        )
                else:
                    # Connector token-based authentication
                    return SeldonGSSecretSchema(
                        name="",
                        rclone_config_gs_token=json.dumps(
                            dict(
                                access_token=gcp_credentials.token,
                            )
                        ),
                    )

            logger.warning(
                "No credentials are configured for the active GCS artifact "
                "store. The Seldon Core model deployer will assume an "
                "implicit form of authentication is available in the "
                "target Kubernetes cluster, but the served model may not "
                "be able to access the model artifacts."
            )
            return SeldonGSSecretSchema(name="", rclone_config_gs_anonymous=False)

        elif artifact_store.flavor == "azure":
            from zenml.integrations.azure.artifact_stores import (
                AzureArtifactStore,
            )

            assert isinstance(artifact_store, AzureArtifactStore)

            azure_credentials = artifact_store.get_credentials()

            if azure_credentials:
                # Convert the credentials into the format expected by Seldon
                # Core
                if azure_credentials.connection_string is not None:
                    try:
                        # We need to extract the account name and key from the
                        # connection string
                        tokens = azure_credentials.connection_string.split(";")
                        token_dict = dict(
                            [token.split("=", maxsplit=1) for token in tokens]
                        )
                        account_name = token_dict["AccountName"]
                        account_key = token_dict["AccountKey"]
                    except (KeyError, ValueError) as e:
                        raise RuntimeError(
                            "The Azure connection string configured for the "
                            "artifact store expected format."
                        ) from e

                    return SeldonAzureSecretSchema(
                        name="",
                        rclone_config_az_account=account_name,
                        rclone_config_az_key=account_key,
                    )

                if azure_credentials.sas_token is not None:
                    return SeldonAzureSecretSchema(
                        name="",
                        rclone_config_az_sas_url=azure_credentials.sas_token,
                    )

                if (
                    azure_credentials.account_name is not None
                    and azure_credentials.account_key is not None
                ):
                    return SeldonAzureSecretSchema(
                        name="",
                        rclone_config_az_account=azure_credentials.account_name,
                        rclone_config_az_key=azure_credentials.account_key,
                    )

                if (
                    azure_credentials.client_id is not None
                    and azure_credentials.client_secret is not None
                    and azure_credentials.tenant_id is not None
                    and azure_credentials.account_name is not None
                ):
                    return SeldonAzureSecretSchema(
                        name="",
                        rclone_config_az_client_id=azure_credentials.client_id,
                        rclone_config_az_client_secret=azure_credentials.client_secret,
                        rclone_config_az_tenant=azure_credentials.tenant_id,
                    )

            logger.warning(
                "No credentials are configured for the active Azure "
                "artifact store. The Seldon Core model deployer will "
                "assume an implicit form of authentication is available "
                "in the target Kubernetes cluster, but the served model "
                "may not be able to access the model artifacts."
            )
            return SeldonAzureSecretSchema(name="", rclone_config_az_env_auth=True)

        raise RuntimeError(
            "The Seldon Core model deployer doesn't know how to configure "
            f"credentials automatically for the `{artifact_store.flavor}` "
            "active artifact store flavor. "
            "Please use one of the supported artifact stores (S3, GCP or "
            "Azure) or specify a ZenML secret in the model deployer "
            "configuration that holds the credentials required to access "
            "the model artifacts."
        )

    def _delete_kubernetes_secret(self, secret_name: str) -> None:
        """Delete a Kubernetes secret associated with this model deployer.

        Do this if no Seldon Core deployments are using it. The only exception
        is if the secret name is the one pre-configured in the model deployer
        configuration.

        Args:
            secret_name: The name of the Kubernetes secret to delete.
        """
        if secret_name == self.config.kubernetes_secret_name:
            return

        # fetch all the Seldon Core deployments that currently
        # configured to use this secret
        services = self.find_model_server()
        for service in services:
            config = cast(SeldonDeploymentConfig, service.config)
            if config.secret_name == secret_name:
                return
        self.seldon_client.delete_secret(secret_name)

    def deploy_model(
        self,
        config: ServiceConfig,
        replace: bool = False,
        timeout: int = DEFAULT_SELDON_DEPLOYMENT_START_STOP_TIMEOUT,
    ) -> BaseService:
        """Create a new Seldon Core deployment or update an existing one.

        # noqa: DAR402

        This should serve the supplied model and deployment configuration.

        This method has two modes of operation, depending on the `replace`
        argument value:

          * if `replace` is False, calling this method will create a new Seldon
            Core deployment server to reflect the model and other configuration
            parameters specified in the supplied Seldon deployment `config`.

          * if `replace` is True, this method will first attempt to find an
            existing Seldon Core deployment that is *equivalent* to the supplied
            configuration parameters. Two or more Seldon Core deployments are
            considered equivalent if they have the same `pipeline_name`,
            `pipeline_step_name` and `model_name` configuration parameters. To
            put it differently, two Seldon Core deployments are equivalent if
            they serve versions of the same model deployed by the same pipeline
            step. If an equivalent Seldon Core deployment is found, it will be
            updated in place to reflect the new configuration parameters. This
            allows an existing Seldon Core deployment to retain its prediction
            URL while performing a rolling update to serve a new model version.

        Callers should set `replace` to True if they want a continuous model
        deployment workflow that doesn't spin up a new Seldon Core deployment
        server for each new model version. If multiple equivalent Seldon Core
        deployments are found, the most recently created deployment is selected
        to be updated and the others are deleted.

        Args:
            config: the configuration of the model to be deployed with Seldon.
                Core
            replace: set this flag to True to find and update an equivalent
                Seldon Core deployment server with the new model instead of
                starting a new deployment server.
            timeout: the timeout in seconds to wait for the Seldon Core server
                to be provisioned and successfully started or updated. If set
                to 0, the method will return immediately after the Seldon Core
                server is provisioned, without waiting for it to fully start.

        Returns:
            The ZenML Seldon Core deployment service object that can be used to
            interact with the remote Seldon Core server.

        Raises:
            SeldonClientError: if a Seldon Core client error is encountered
                while provisioning the Seldon Core deployment server.
            RuntimeError: if `timeout` is set to a positive value that is
                exceeded while waiting for the Seldon Core deployment server
                to start, or if an operational failure is encountered before
                it reaches a ready state.
        """
        with track_handler(AnalyticsEvent.MODEL_DEPLOYED) as analytics_handler:
            config = cast(SeldonDeploymentConfig, config)
            service = None

            # if replace is True, find equivalent Seldon Core deployments
            if replace is True:
                equivalent_services = self.find_model_server(
                    running=False,
                    pipeline_name=config.pipeline_name,
                    pipeline_step_name=config.pipeline_step_name,
                    model_name=config.model_name,
                )

                for equivalent_service in equivalent_services:
                    if service is None:
                        # keep the most recently created service
                        service = equivalent_service
                    else:
                        try:
                            # delete the older services and don't wait for
                            # them to be deprovisioned
                            service.stop()
                        except RuntimeError:
                            # ignore errors encountered while stopping old
                            # services
                            pass

            # if a custom Kubernetes secret is not explicitly specified in the
            # SeldonDeploymentConfig, try to create one from the ZenML secret
            # configured for the model deployer
            config.secret_name = (
                config.secret_name or self._create_or_update_kubernetes_secret()
            )

            if service:
                # update an equivalent service in place
                service.update(config)
                logger.info(
                    f"Updating an existing Seldon deployment service: {service}"
                )
            else:
                # create a new service
                service = SeldonDeploymentService(config=config)
                logger.info(f"Creating a new Seldon deployment service: {service}")

            # start the service which in turn provisions the Seldon Core
            # deployment server and waits for it to reach a ready state
            service.start(timeout=timeout)

            # Add telemetry with metadata that gets the stack metadata and
            # differentiates between pure model and custom code deployments
            stack = Client().active_stack
            stack_metadata = {
                component_type.value: component.flavor
                for component_type, component in stack.components.items()
            }
            analytics_handler.metadata = {
                "store_type": Client().zen_store.type.value,
                **stack_metadata,
                "is_custom_code_deployment": config.is_custom_deployment,
            }

        return service

    def find_model_server(
        self,
        running: bool = False,
        service_uuid: Optional[UUID] = None,
        pipeline_name: Optional[str] = None,
        run_name: Optional[str] = None,
        pipeline_step_name: Optional[str] = None,
        model_name: Optional[str] = None,
        model_uri: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> List[BaseService]:
        """Find one or more Seldon Core model services that match the given criteria.

        The Seldon Core deployment services that meet the search criteria are
        returned sorted in descending order of their creation time (i.e. more
        recent deployments first).

        Args:
            running: if true, only running services will be returned.
            service_uuid: the UUID of the Seldon Core service that was
                originally used to create the Seldon Core deployment resource.
            pipeline_name: name of the pipeline that the deployed model was part
                of.
            run_name: Name of the pipeline run which the deployed model was
                part of.
            pipeline_step_name: the name of the pipeline model deployment step
                that deployed the model.
            model_name: the name of the deployed model.
            model_uri: URI of the deployed model.
            model_type: the Seldon Core server implementation used to serve
                the model

        Returns:
            One or more Seldon Core service objects representing Seldon Core
            model servers that match the input search criteria.
        """
        # Use a Seldon deployment service configuration to compute the labels
        config = SeldonDeploymentConfig(
            pipeline_name=pipeline_name or "",
            run_name=run_name or "",
            pipeline_run_id=run_name or "",
            pipeline_step_name=pipeline_step_name or "",
            model_name=model_name or "",
            model_uri=model_uri or "",
            implementation=model_type or "",
        )
        labels = config.get_seldon_deployment_labels()
        if service_uuid:
            # the service UUID is not a label covered by the Seldon
            # deployment service configuration, so we need to add it
            # separately
            labels["zenml.service_uuid"] = str(service_uuid)

        deployments = self.seldon_client.find_deployments(labels=labels)
        # sort the deployments in descending order of their creation time
        deployments.sort(
            key=lambda deployment: datetime.strptime(
                deployment.metadata.creationTimestamp,
                "%Y-%m-%dT%H:%M:%SZ",
            )
            if deployment.metadata.creationTimestamp
            else datetime.min,
            reverse=True,
        )

        services: List[BaseService] = []
        for deployment in deployments:
            # recreate the Seldon deployment service object from the Seldon
            # deployment resource
            service = SeldonDeploymentService.create_from_deployment(
                deployment=deployment
            )
            if running and not service.is_running:
                # skip non-running services
                continue
            services.append(service)

        return services

    def stop_model_server(
        self,
        uuid: UUID,
        timeout: int = DEFAULT_SELDON_DEPLOYMENT_START_STOP_TIMEOUT,
        force: bool = False,
    ) -> None:
        """Stop a Seldon Core model server.

        Args:
            uuid: UUID of the model server to stop.
            timeout: timeout in seconds to wait for the service to stop.
            force: if True, force the service to stop.

        Raises:
            NotImplementedError: stopping Seldon Core model servers is not
                supported.
        """
        raise NotImplementedError(
            "Stopping Seldon Core model servers is not implemented. Try "
            "deleting the Seldon Core model server instead."
        )

    def start_model_server(
        self,
        uuid: UUID,
        timeout: int = DEFAULT_SELDON_DEPLOYMENT_START_STOP_TIMEOUT,
    ) -> None:
        """Start a Seldon Core model deployment server.

        Args:
            uuid: UUID of the model server to start.
            timeout: timeout in seconds to wait for the service to become
                active. . If set to 0, the method will return immediately after
                provisioning the service, without waiting for it to become
                active.

        Raises:
            NotImplementedError: since we don't support starting Seldon Core
                model servers
        """
        raise NotImplementedError(
            "Starting Seldon Core model servers is not implemented"
        )

    def delete_model_server(
        self,
        uuid: UUID,
        timeout: int = DEFAULT_SELDON_DEPLOYMENT_START_STOP_TIMEOUT,
        force: bool = False,
    ) -> None:
        """Delete a Seldon Core model deployment server.

        Args:
            uuid: UUID of the model server to delete.
            timeout: timeout in seconds to wait for the service to stop. If
                set to 0, the method will return immediately after
                deprovisioning the service, without waiting for it to stop.
            force: if True, force the service to stop.
        """
        services = self.find_model_server(service_uuid=uuid)
        if len(services) == 0:
            return

        service = services[0]

        assert isinstance(service, SeldonDeploymentService)
        service.stop(timeout=timeout, force=force)

        if service.config.secret_name:
            # delete the Kubernetes secret used to store the authentication
            # information for the Seldon Core model server storage initializer
            # if no other Seldon Core model servers are using it
            self._delete_kubernetes_secret(service.config.secret_name)
