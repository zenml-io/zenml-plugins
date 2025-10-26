# Quick Setup Guide for SLURM Orchestrator

## 1. Install Dependencies

```bash
cd /Users/htahir1/Workspace/zenml-plugins/slurm_orchestrator
pip install -r requirements.txt
```

## 2. Initialize ZenML

```bash
zenml init
```

## 3. Register the Orchestrator Flavor

```bash
zenml orchestrator flavor register orchestrator.slurm_orchestrator.SlurmOrchestratorFlavor
```

Verify it was registered:

```bash
zenml orchestrator flavor list
```

## 4. Register an Orchestrator Instance

Basic registration:

```bash
zenml orchestrator register my_slurm_orchestrator -f slurm
```

Or with custom settings:

```bash
zenml orchestrator register my_slurm_orchestrator -f slurm \
  --partition=gpu \
  --account=my_account \
  --qos=standard \
  --job_name_prefix=zenml_job \
  --output_dir=/scratch/zenml_logs
```

## 5. Create a Stack

```bash
# Register stack with SLURM orchestrator and default artifact store
zenml stack register slurm_stack -o my_slurm_orchestrator -a default

# Set it active
zenml stack set slurm_stack
```

## 6. Run the Example Pipeline

```bash
python run.py
```

This will:
- Load the Iris dataset
- Split into train/test sets
- Train a Random Forest classifier
- Evaluate the model
- Submit all steps to SLURM as containerized jobs with automatic dependency management

## Monitoring Jobs

From the login node or local machine:

```bash
# Check running SLURM jobs
squeue -u $USER

# Check job output
cat /scratch/zenml_logs/zenml_importer_*.out

# Check specific job
sacct -j JOB_ID
```

## Key Features

✅ **Settings-based configuration** - All parameters are customizable via settings
✅ **Docker container support** - Steps run in containerized environments
✅ **Automatic job dependencies** - SLURM manages step ordering via job dependencies
✅ **Resource specifications** - CPU, memory, GPU, time limits support
✅ **Synchronous/asynchronous modes** - Control whether to wait for completion
✅ **Per-step customization** - Override settings for individual steps

## Architecture

```
Pipeline Submission
    ↓
For each step:
    ├─ Get Docker image (from image builder)
    ├─ Generate SLURM batch script
    ├─ Submit via sbatch
    ├─ Track job ID
    └─ Set dependencies for downstream steps
    ↓
If synchronous:
    └─ Wait for job completion via squeue
```

## Generated SLURM Script Example

```bash
#!/bin/bash
#SBATCH --job-name=zenml_importer
#SBATCH --partition=default
#SBATCH --output=/scratch/zenml_logs/zenml_importer_%j.out

export ZENML_SLURM_ORCHESTRATOR_RUN_ID='uuid-123'
export ZENML_LOCAL_STORES_PATH='/home/user/.zenml'

docker run --rm \
  -v /home/user/.zenml:/home/user/.zenml \
  -e ZENML_SLURM_ORCHESTRATOR_RUN_ID='uuid-123' \
  my-pipeline-image:latest \
  python -m zenml.orchestrators.step_runner --step-name=importer --snapshot-id=snapshot123
```

## Troubleshooting

**Jobs not submitting?**
- Ensure `sbatch` is available: `which sbatch && sbatch --version`
- Check cluster access: `sinfo` and `squeue -u $USER`

**Docker not found in jobs?**
- Verify Docker is installed on compute nodes: `docker --version`
- Check Docker daemon is running

**Artifacts not accessible?**
- Ensure artifact store paths are accessible from compute nodes
- Test from a login node: `ls -la /path/to/store`

## Next Steps

See [README.md](README.md) for:
- Detailed configuration options
- Per-step customization examples
- Advanced features and best practices
- Complete API documentation
