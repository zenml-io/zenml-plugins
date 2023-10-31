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
"""BentoML model deployer flavor."""

from typing import TYPE_CHECKING, Optional, Type

from zenml.model_deployers.base_model_deployer import (
    BaseModelDeployerConfig,
    BaseModelDeployerFlavor,
)

if TYPE_CHECKING:
    from hf_sagemaker_model_deployer import HFSagemakerModelDeployer


HF_SAGEMAKER_MODEL_DEPLOYER_FLAVOR = "hf_sagemaker"


class HFSagemakerModelDeployerConfig(BaseModelDeployerConfig):
    """Configuration for the HFSagemakerModelDeployer."""

    service_path: str = ""


class HFSagemakerModelDeployerFlavor(BaseModelDeployerFlavor):
    """Flavor for the Huggingface Sagemaker model deployer."""

    @property
    def name(self) -> str:
        """Name of the flavor.

        Returns:
            Name of the flavor.
        """
        return HF_SAGEMAKER_MODEL_DEPLOYER_FLAVOR


    @property
    def config_class(self) -> Type[HFSagemakerModelDeployerConfig]:
        """Returns `HFSagemakerModelDeployerConfig` config class.

        Returns:
                The config class.
        """
        return HFSagemakerModelDeployerConfig

    @property
    def implementation_class(self) -> Type["HFSagemakerModelDeployer"]:
        """Implementation class for this flavor.

        Returns:
            The implementation class.
        """
        from hf_sagemaker_model_deployer import (
            HFSagemakerModelDeployer,
        )

        return HFSagemakerModelDeployer
