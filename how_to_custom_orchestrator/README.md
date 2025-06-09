# 🎼 Create a Custom Orchestrator with ZenML

ZenML allows you to create a custom orchestrator, an essential component in any MLOps stack responsible for running your machine learning pipelines. This tutorial guides you through the process of creating an orchestrator that runs each step of a pipeline locally in a docker container.

## ❓Why would you need a custom orchestrator?

While ZenML comes built with standard integrations for well-known orchestrators like [Airflow](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/airflow), [Kubeflow](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/kubeflow), and even running [locally](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/local), your business might either want to orchestrate your ML workloads differently or slightly tweak the implementations of the standard orchestrators. In this case, this guide is useful, as it implements a relatively simple orchestrator.

## 📚 Overview

The `BaseOrchestrator` abstracts away many of the ZenML-specific details from the actual implementation and exposes a simplified interface. This example is an end-to-end guide on creating a custom orchestrator using ZenML. Click [here](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/custom) to learn more about the custom orchestrator interface.

## 💻 Running it Locally

### 📑 Prerequisites

To run this example, you need to have ZenML installed along with the necessary dependencies. You can do so by executing the following commands:

```shell
# clone the ZenML plugin repository
git clone git@github.com:zenml-io/zenml-plugins.git

# navigate to the custom orchestrator directory
cd zenml-plugins/how_to_custom_orchestrator

# install the necessary dependencies
pip install -r requirements.txt
```

### 🚀 Registering the Custom Orchestrator

First, you have to initialize zenml

```shell
zenml init
```

Then, you need to register the flavor of the orchestrator:

```shell
# register the flavor of the orchestrator
zenml orchestrator flavor register orchestrator.my_docker_orchestrator.MyDockerOrchestratorFlavor 
```

Then, you register your custom orchestrator using your registered flavor:

```shell
# register the custom orchestrator
zenml orchestrator register my_docker_orchestrator -f my_docker  
```

### 📝 Registering and Setting the Stack

Next, you need to register a stack with your custom orchestrator and the default artifact store attached:

```shell
# register the stack
zenml stack register my_stack -o my_docker_orchestrator -a default
```

Finally, set the stack active. This means every pipeline that runs will use the custom orchestrator:

```shell
# set the stack active
zenml stack set my_stack
```

You can then run the pipeline:

```shell
# set the stack active
python run.py
```

## 🚀 Modal Orchestrator (NEW!)

This repository now includes a **Modal orchestrator** that runs entire pipelines in a single Modal function for maximum speed and efficiency. Unlike the Modal step operator which runs individual steps, this orchestrator eliminates startup overhead by running the complete pipeline in one Modal environment.

### ✨ Key Advantages

- **Speed**: No startup overhead between steps
- **Parallelism**: Steps run in parallel using ThreadedDagRunner
- **Cost Efficiency**: Single Modal session vs. multiple step executions  
- **Simplicity**: One Modal function handles the entire pipeline
- **Resource Optimization**: Shared environment for all pipeline steps

### 🔧 Setting Up the Modal Orchestrator

First, ensure you have Modal installed and authenticated:

```shell
# Install Modal
pip install modal

# Authenticate with Modal (requires Modal account)
modal setup
```

Register the Modal orchestrator flavor and component:

```shell
# Register the Modal orchestrator flavor
zenml orchestrator flavor register orchestrator.modal_orchestrator.ModalOrchestratorFlavor

# Option 1: Register with minimal config (uses Modal defaults)
zenml orchestrator register modal_orchestrator -f modal

# Option 2: Register with comprehensive config  
zenml orchestrator register modal_orchestrator -f modal \
  --token=mo-your-modal-token-here \
  --cpu_count=4 \
  --memory_mb=8192 \
  --gpu=A100 \
  --region=us-west-2 \
  --cloud=aws \
  --timeout=7200 \
  --keep_warm=2 \
  --concurrency_limit=5
```

Create and set a stack with the Modal orchestrator:

```shell
# Create stack with Modal orchestrator
zenml stack register modal_stack -o modal_orchestrator -a default

# Set as active stack
zenml stack set modal_stack
```

**Important Requirements:**
- Remote container registry (e.g., AWS ECR, Docker Hub, GCR)
- Remote artifact store (e.g., S3, GCS, Azure Blob)
- Modal authentication configured

### 🏃‍♂️ Running Pipelines with Modal

Once set up, simply run your pipeline:

```shell
python run.py
```

The entire sklearn pipeline (data loading, training, evaluation) will run in a single Modal function!

### ⚙️ Configuration Options

The Modal orchestrator supports comprehensive configuration options:

### 🔧 Orchestrator Configuration

```python
# When registering the orchestrator
from zenml import Client

client = Client()
client.create_orchestrator(
    name="modal_orchestrator",
    flavor="modal",
    configuration={
        # Authentication (optional)
        "token": "mo-your-modal-token-here",
        "workspace": "your-workspace", 
        "environment": "main",
        
        # Default resources
        "cpu_count": 4,
        "memory_mb": 8192,  # 8GB
        "gpu": "A100",
        
        # Modal settings
        "region": "us-west-2",
        "cloud": "aws",
        "timeout": 7200,  # 2 hours
        "min_containers": 2,   # Keep 2 containers warm (Modal 1.0)
        "max_containers": 10,  # Max 10 concurrent containers (Modal 1.0)
        
        # Parallelism settings
        "max_parallelism": 4,  # Run up to 4 steps in parallel
        "parallel_step_startup_wait": 1.0,  # 1s delay between starts
    }
)
```

### ⚙️ Pipeline-Level Settings

```python
from zenml.config import ResourceSettings
from orchestrator.modal_orchestrator import ModalOrchestratorSettings

# Override per-pipeline settings
modal_settings = ModalOrchestratorSettings(
    gpu="H100",           # Override default GPU
    region="us-east-1",   # Override region
    cpu_count=8,          # Override CPU
    memory_mb=16384,      # Override memory (16GB)
    timeout=3600,         # Override timeout (1 hour)
    max_parallelism=8,    # Allow up to 8 parallel steps
    parallel_step_startup_wait=0.5,  # 0.5s delay between starts
)

# ZenML resource settings (still supported)
resource_settings = ResourceSettings(
    cpu=8,
    memory="16GB", 
    gpu_count=2
)

# Apply to pipeline (settings override config defaults)
@pipeline(
    settings={
        "orchestrator": modal_settings,
        "resources": resource_settings  # Fallback if orchestrator settings not provided
    }
)
def my_modal_pipeline():
    # Your pipeline steps
    pass
```

### 📋 Configuration Options

| Setting | Type | Description | Default |
|---------|------|-------------|---------|
| `token` | str | Modal API token | Uses `~/.modal.toml` |
| `workspace` | str | Modal workspace | Default workspace |
| `environment` | str | Modal environment | Default environment |
| `cpu_count` | int | CPU cores per pipeline | Pipeline resource settings |
| `memory_mb` | int | Memory in MB | Pipeline resource settings |
| `gpu` | str | GPU type (T4, A100, H100, etc.) | None |
| `region` | str | Modal region | Modal default |
| `cloud` | str | Cloud provider (aws, gcp) | Modal default |
| `timeout` | int | Max execution time (seconds) | 86400 (24h) |
| `min_containers` | int | Min containers to keep warm (Modal 1.0) | None |
| `max_containers` | int | Max concurrent containers (Modal 1.0) | None |
| `max_parallelism` | int | Max parallel step execution | No limit |
| `parallel_step_startup_wait` | float | Delay between parallel step starts (seconds) | 0.0 |

### 📊 Comparison: Modal Step Operator vs Modal Orchestrator

| Feature | Modal Step Operator | Modal Orchestrator |
|---------|-------------------|-------------------|
| Execution | Individual steps | Entire pipeline |
| Parallelism | None (sequential) | **ThreadedDagRunner (parallel)** |
| Startup Overhead | Per step | Once per pipeline |
| Cost | Higher (multiple sessions) | Lower (single session) |
| Speed | Slower | **Faster (parallel + no overhead)** |
| Resource Usage | Per step configuration | Pipeline-wide configuration |
| Use Case | Complex resource needs per step | Fast, parallel pipeline execution |

### 🧪 Testing

A test script is provided to validate the setup:

```shell
python test_modal_orchestrator.py
```

This script will register the Modal orchestrator and create a test stack.

## 📚 Learn More

For more information on creating a custom orchestrator in ZenML, follow this [guide](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators).