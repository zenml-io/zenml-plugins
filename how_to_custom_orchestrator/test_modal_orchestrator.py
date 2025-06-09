#!/usr/bin/env python3
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
"""Test script for Modal orchestrator registration and basic functionality."""

from zenml.client import Client


def register_modal_orchestrator():
    """Register the Modal orchestrator flavor and component."""
    client = Client()
    
    print("🔧 Registering Modal orchestrator flavor...")
    try:
        # Register the flavor
        client.create_flavor(
            source="orchestrator.modal_orchestrator.ModalOrchestratorFlavor",
            component_type="orchestrator"
        )
        print("✅ Modal orchestrator flavor registered successfully!")
    except Exception as e:
        if "already exists" in str(e) or "Found an existing flavor" in str(e):
            print("ℹ️  Modal orchestrator flavor already exists")
        else:
            print(f"❌ Failed to register flavor: {e}")
            return False
    
    print("🎼 Registering Modal orchestrator component...")
    try:
        # Register the orchestrator with configuration  
        client.create_stack_component(
            name="modal_orchestrator",
            flavor="modal",
            component_type="orchestrator",
            configuration={
                # Modal authentication (optional - falls back to ~/.modal.toml)
                # "token": "mo-your-modal-token-here",  
                # "workspace": "your-workspace",
                # "environment": "main",
                
                # Default resource settings
                "cpu_count": 2,
                "memory_mb": 4096,  # 4GB
                "timeout": 3600,    # 1 hour (instead of 24h default)
                
                # Modal-specific settings
                "gpu": "T4",        # Default GPU type
                "region": "us-east-1",
                "cloud": "aws",
                "min_containers": 1,     # Keep 1 container warm (Modal 1.0)
                "max_containers": 10,    # Max 10 concurrent containers (Modal 1.0)
                
                # Parallelism settings
                "max_parallelism": 4,  # Run up to 4 steps in parallel
                "parallel_step_startup_wait": 1.0,  # 1 second delay between parallel starts
            }
        )
        print("✅ Modal orchestrator component registered successfully!")
        print("   📝 Configured with:")
        print("   - Default CPU: 2 cores")
        print("   - Default Memory: 4GB") 
        print("   - Default GPU: T4")
        print("   - Timeout: 1 hour")
        print("   - Min containers: 1 (warm)")
        print("   - Max containers: 10 (concurrent)")
        print("   - Max parallelism: 4 steps")
        print("   - Parallel startup delay: 1s")
    except Exception as e:
        if "already exists" in str(e):
            print("ℹ️  Modal orchestrator component already exists")
        else:
            print(f"❌ Failed to register orchestrator: {e}")
            return False
    
    return True


def create_modal_stack():
    """Create a stack with the Modal orchestrator."""
    client = Client()
    
    print("📚 Creating stack with Modal orchestrator...")
    try:
        # Create stack with Modal orchestrator
        client.create_stack(
            name="modal_stack",
            components={
                "orchestrator": client.get_stack_component("modal_orchestrator").id,
                "artifact_store": client.get_stack_component("default").id
            }
        )
        print("✅ Modal stack created successfully!")
    except Exception as e:
        if "already exists" in str(e):
            print("ℹ️  Modal stack already exists")
        else:
            print(f"❌ Failed to create stack: {e}")
            return False
    
    return True


def test_modal_orchestrator():
    """Test the Modal orchestrator setup."""
    print("🚀 Testing Modal Orchestrator Setup")
    print("=" * 50)
    
    # Register Modal orchestrator
    if not register_modal_orchestrator():
        print("❌ Failed to register Modal orchestrator")
        return
    
    # Create Modal stack 
    if not create_modal_stack():
        print("❌ Failed to create Modal stack")
        return
    
    print("\n🎉 Modal orchestrator setup completed successfully!")
    print("\nNext steps:")
    print("1. Set up Modal authentication: modal setup")
    print("2. Set the Modal stack as active: zenml stack set modal_stack")
    print("3. Run your pipeline: python run.py")
    print("\nNote: Make sure you have:")
    print("- A remote container registry configured")
    print("- A remote artifact store configured")
    print("- Modal authentication set up")


if __name__ == "__main__":
    test_modal_orchestrator()