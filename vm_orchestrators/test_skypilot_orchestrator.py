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

import pytest
from contextlib import ExitStack as does_not_raise
from datetime import datetime
from uuid import uuid4
from zenml.enums import StackComponentType
from zenml.exceptions import StackValidationError
from zenml.stack import Stack

from orchestrator.skypilot_orchestrator import SkypilotOrchestrator, SkypilotOrchestratorConfig, SkypilotOrchestratorSettings 

SKY_STACK = "skypilot_stack"

def _get_skypilot_orchestrator(local: bool = False) -> SkypilotOrchestrator:
    """Helper function to get a Skypilot orchestrator."""
    return SkypilotOrchestrator(
        name="",
        id=uuid4(),
        config=SkypilotOrchestratorConfig(
            sky_stack= SKY_STACK,
            local=local,
        ),
        flavor="vm",
        type=StackComponentType.ORCHESTRATOR,
        user=uuid4(),
        workspace=uuid4(),
        created=datetime.now(),
        updated=datetime.now(),
    )

def test_skypilot_orchestrator_remote_stack(s3_artifact_store, remote_container_registry) -> None:
    """Test the remote and local skypilot orchestrator with remote stacks."""

    # Test remote stack with remote orchestrator
    orchestrator = _get_skypilot_orchestrator()
    with does_not_raise():
        Stack(
            id=uuid4(),
            name="",
            orchestrator=orchestrator,
            artifact_store=s3_artifact_store,
            container_registry=remote_container_registry,
        ).validate()

    # Test remote stack with local orchestrator
    orchestrator = _get_skypilot_orchestrator(local=True)
    with pytest.raises(StackValidationError):
        Stack(
            id=uuid4(),
            name="",
            orchestrator=orchestrator,
            artifact_store=s3_artifact_store,
            container_registry=remote_container_registry,
        ).validate()

def test_skypilot_orchestrator_local_stack(local_artifact_store, local_container_registry) -> None:
    """Test the remote and local skypilot orchestrator with local stacks."""

    # Test missing container registry
    orchestrator = _get_skypilot_orchestrator(local=True)
    with pytest.raises(StackValidationError):
        Stack(
            id=uuid4(),
            name="",
            orchestrator=orchestrator,
            artifact_store=local_artifact_store,
        ).validate()

    # Test local stack with remote orchestrator
    orchestrator = _get_skypilot_orchestrator()
    with pytest.raises(StackValidationError):
        Stack(
            id=uuid4(),
            name="",
            orchestrator=orchestrator,
            artifact_store=local_artifact_store,
            container_registry=local_container_registry,
        ).validate()

    # Test local stack with local orchestrator
    orchestrator = _get_skypilot_orchestrator(local=True)
    with does_not_raise():
        Stack(
            id=uuid4(),
            name="",
            orchestrator=orchestrator,
            artifact_store=local_artifact_store,
            container_registry=local_container_registry,
        ).validate()


def test_skypilot_orchestrator_settings(mocker):
    """Test for Skypilot orchestrator settings."""
    orchestrator = _get_skypilot_orchestrator(local=True)

    settings = SkypilotOrchestratorSettings(
        instance_type="t-large",
        cpus=4,
        memory="8",
        accelerators="V100:2",
        accelerator_args={"tpu_vm": True, "runtime_version": "tpu-vm-base"},
        use_spot=True,
        spot_recovery="spot_recovery_strategy",
        region="region-1",
        zone="zone-1",
        image_id="image_id-1",
        disk_size=100,
        disk_tier="medium",
        cluster_name="cluster-1",
        retry_until_up=True,
        idle_minutes_to_autostop=30,
        down=True,
        stream_logs=True,
    )
    assert orchestrator.config.is_local == False
    assert orchestrator.settings_class == SkypilotOrchestratorSettings
    assert orchestrator.get_settings() == settings
    assert orchestrator.get_settings().to_dict() == settings.to_dict()
