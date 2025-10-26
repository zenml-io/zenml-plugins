# 🎼 SLURM Orchestrator for ZenML

A custom ZenML orchestrator that runs pipelines on HPC clusters using SLURM (Simple Linux Utility for Resource Management). This orchestrator submits each pipeline step as a containerized SLURM job with automatic dependency management and resource allocation.

## ❓ Why a SLURM Orchestrator?

If you're running machine learning workloads on high-performance computing (HPC) clusters managed by SLURM, this orchestrator allows you to:

- **Leverage cluster resources**: Submit jobs to SLURM partitions with specific resource requirements (CPU, memory, GPU, time limits)
- **Maintain consistency**: Run containerized workloads using Docker, ensuring reproducible environments across all compute nodes
- **Automatic orchestration**: ZenML manages step dependencies via SLURM job dependencies
- **Seamless integration**: Use the same pipeline code locally and on your HPC cluster

## 📚 Overview

The `SlurmOrchestrator` inherits from `ContainerizedOrchestrator` and provides the following features:

- **SLURM Job Submission**: Generates SLURM batch scripts and submits them via `sbatch`
- **Docker Integration**: Runs pipeline steps in Docker containers on compute nodes
- **Dependency Management**: Uses SLURM's `--dependency=afterok:job_id` for automatic step ordering
- **Resource Specifications**: Maps ZenML resource settings to SLURM directives (CPU, memory, GPU, time)
- **Configurable Execution**: Support for synchronous (wait for completion) and asynchronous modes
- **Flexible Configuration**: Per-stack and per-step configuration options

## 💻 Getting Started

### Prerequisites

Before using this orchestrator, ensure you have:

1. **SLURM cluster access**: Access to an HPC cluster with SLURM installed
2. **Docker on compute nodes**: Docker daemon running on all compute nodes (or nodes you'll use)
3. **ZenML installed**: `pip install zenml>=0.50.0`
4. **ZenML repository initialized**: `zenml init` in your project root

### Installation

Clone the repository and install dependencies:

```bash
# Clone the ZenML plugins repository
git clone https://github.com/zenml-io/zenml-plugins.git

# Navigate to the SLURM orchestrator directory
cd zenml-plugins/slurm_orchestrator

# Install required dependencies
pip install -r requirements.txt
```

### 🚀 Registering the Custom Orchestrator

#### 1. Register the Orchestrator Flavor

Register the SLURM orchestrator flavor:

```bash
zenml orchestrator flavor register orchestrator.slurm_orchestrator.SlurmOrchestratorFlavor
```

Verify the flavor is registered:

```bash
zenml orchestrator flavor list
```

You should see `slurm` in the list of available flavors.

#### 2. Register an Orchestrator Instance

Register a SLURM orchestrator with your desired configuration:

```bash
# Basic registration with defaults
zenml orchestrator register my_slurm_orchestrator -f slurm

# Or with custom configuration
zenml orchestrator register my_slurm_orchestrator -f slurm \
  --partition=gpu \
  --account=ml_project \
  --qos=standard \
  --job_name_prefix=zenml_job \
  --output_dir=/scratch/zenml_logs
```

**Configuration Options**:

| Option | Default | Description |
|--------|---------|-------------|
| `partition` | `default` | SLURM partition to submit jobs to |
| `account` | `None` | SLURM account/project name (optional) |
| `qos` | `None` | Quality of Service level (optional) |
| `job_name_prefix` | `zenml` | Prefix for SLURM job names |
| `output_dir` | `/tmp/zenml_slurm_logs` | Directory to store SLURM logs |
| `is_synchronous` | `True` | Wait for job completion before returning |

#### 3. Create a Stack with the Orchestrator

Create a new ZenML stack that uses your SLURM orchestrator:

```bash
# Register the stack with the SLURM orchestrator and default artifact store
zenml stack register slurm_stack -o my_slurm_orchestrator -a default

# Set it as the active stack
zenml stack set slurm_stack
```

Verify the stack is set:

```bash
zenml stack list
zenml stack get slurm_stack
```

## 🏃 Running a Pipeline

### Using the Example Pipeline

Once your stack is configured, run the example pipeline:

```bash
python run.py
```

This will:
1. Load the Iris dataset
2. Split it into train/test sets
3. Train a Random Forest classifier
4. Evaluate the model
5. Return the accuracy

Each step runs as a separate SLURM job with automatic dependency management.

### Monitoring Jobs

While the pipeline runs, monitor SLURM jobs from your local machine or the login node:

```bash
# Check running jobs
squeue -u $USER

# Check job details
sinfo

# View job output (after completion)
cat /tmp/zenml_slurm_logs/zenml_step_name_JOBID.out
```

### Using Your Own Pipeline

To run your own pipeline with the SLURM orchestrator:

1. Define your pipeline and steps as usual in ZenML
2. Ensure all dependencies are available in your Docker image
3. Set the SLURM stack as active: `zenml stack set slurm_stack`
4. Run your pipeline: `python your_pipeline.py`

## ⚙️ Configuration Examples

### Example 1: GPU-Accelerated Pipeline

Configure the orchestrator for GPU workloads:

```bash
zenml orchestrator register gpu_orchestrator -f slurm \
  --partition=gpu \
  --sbatch_args='{"gpus": "1", "mem": "32G", "cpus-per-task": "8"}'
```

In your pipeline, specify GPU resources per step:

```python
from zenml import step
from zenml.config.resource_settings import ResourceSettings

@step(settings={"resources": ResourceSettings(gpu="1")})
def gpu_step():
    # This step runs on GPU
    pass
```

### Example 2: Long-Running Job with Extended Time Limit

```bash
zenml orchestrator register long_job_orchestrator -f slurm \
  --partition=batch \
  --sbatch_args='{"time": "24:00:00"}'  # 24-hour time limit
```

### Example 3: Specific Account and QOS

```bash
zenml orchestrator register project_orchestrator -f slurm \
  --account=research_group \
  --qos=priority \
  --partition=compute
```

## 📝 Architecture & Implementation Details

### How It Works

1. **Pipeline Submission**: When you run a pipeline, the SLURM orchestrator receives the pipeline snapshot
2. **Script Generation**: For each step, a SLURM batch script is generated containing:
   - SLURM directives (partition, resources, time limit, etc.)
   - Environment variable exports
   - Docker run command with the step's container image and entrypoint
3. **Job Submission**: Scripts are submitted via `sbatch`
4. **Dependency Management**: SLURM job IDs are extracted and used to set dependencies for subsequent steps via `--dependency=afterok:job_id`
5. **Synchronous Waiting** (optional): If configured as synchronous, the orchestrator polls job status via `squeue` until completion

### Generated SLURM Script Example

```bash
#!/bin/bash
#SBATCH --job-name=zenml_importer
#SBATCH --partition=default
#SBATCH --output=/tmp/zenml_slurm_logs/zenml_importer_%j.out
#SBATCH --error=/tmp/zenml_slurm_logs/zenml_importer_%j.err

# Set environment variables
export ZENML_SLURM_ORCHESTRATOR_RUN_ID='12345-abcd-5678'
export ZENML_LOCAL_STORES_PATH='/home/user/.zenml/local_store'

# Run step in Docker
docker run --rm \
  -v /home/user/.zenml:/home/user/.zenml \
  -e ZENML_SLURM_ORCHESTRATOR_RUN_ID='12345-abcd-5678' \
  my-pipeline-image:latest \
  python -m zenml.orchestrators.step_runner --step-name=importer --snapshot-id=12345
```

## 🔧 Advanced Features

### Per-Step Configuration

Use ZenML's settings to customize behavior per step:

```python
from zenml import step
from zenml.config.base_settings import BaseSettings
from orchestrator.slurm_orchestrator import SlurmOrchestratorSettings

custom_settings = SlurmOrchestratorSettings(
    sbatch_args={"time": "02:00:00", "mem": "16G"}
)

@step(settings={"orchestrator": custom_settings})
def my_step():
    pass
```

### Resource Specifications

Define step resource requirements:

```python
from zenml import step
from zenml.config.resource_settings import ResourceSettings

@step(settings={"resources": ResourceSettings(
    cpu_count=4,
    memory="16G",
    gpu="1",
)})
def compute_intensive_step():
    pass
```

## 📊 Supported Execution Modes

The SLURM orchestrator supports the following execution modes:

- **FAIL_FAST**: Stop on first step failure
- **STOP_ON_FAILURE**: Stop on any step failure, but complete running steps
- **CONTINUE_ON_FAILURE**: Continue despite failures (useful for debugging)

Set execution mode when registering your stack or in pipeline configuration.

## ⚠️ Important Considerations

### Docker on Compute Nodes

- Ensure Docker is installed on all compute nodes
- Docker daemon must be running and accessible to cluster users
- Consider security implications of Docker access on shared HPC clusters

### Storage and Artifact Management

- All artifact stores must be accessible from compute nodes (typically shared filesystem)
- Configure your artifact store to use paths accessible on compute nodes
- Ensure proper permissions on shared storage directories

### Environment Setup

- The container image must include all pipeline dependencies
- Use an image builder in your ZenML stack to build images with required dependencies
- Test your Docker image on compute nodes before running pipelines

### Job Logs

- SLURM output files are stored in the configured `output_dir`
- Monitor logs for troubleshooting step failures
- Clean up old logs periodically to avoid filling shared storage

## 🐛 Troubleshooting

### Jobs Not Submitting

```bash
# Check sbatch is available
which sbatch
sbatch --version

# Check permissions and quota
sinfo
squeue -u $USER
```

### Docker Not Found in Jobs

Ensure Docker is installed and available on compute nodes:

```bash
# On compute node
docker --version
docker ps
```

### Artifacts Not Found

Verify artifact store paths are accessible from compute nodes:

```bash
# Check from login node
ls -la /path/to/artifact/store

# Or in a job script
srun ls -la /path/to/artifact/store
```

## 📚 Learn More

For more information on creating custom orchestrators in ZenML, see:

- [ZenML Custom Orchestrator Guide](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/custom)
- [ZenML Stack Configuration](https://docs.zenml.io/stacks-and-components/stacks)
- [ZenML Pipelines Documentation](https://docs.zenml.io/user-guides/build-with-zenml/pipelines)

## 📄 License

This project is licensed under the Apache License 2.0. See the LICENSE file in the ZenML repository for details.

## 🤝 Contributing

Contributions are welcome! Please follow ZenML's contribution guidelines when submitting pull requests.
