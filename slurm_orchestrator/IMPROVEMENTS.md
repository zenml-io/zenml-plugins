# Areas for Improvement - SLURM Orchestrator

## Critical Issues to Address

### 1. ⚠️ Environment Variable Escaping (HIGH PRIORITY)
**Issue**: Line 193 in `_generate_slurm_script`
```python
script += f"export {key}='{value}'\n"
```

**Problem**: If an environment variable value contains a single quote, it will break the shell script.
- Example: `SOME_VAR="path/with'quote"` → `export SOME_VAR='path/with'quote'` ❌

**Fix**:
```python
# Use proper shell escaping
import shlex
script += f"export {key}={shlex.quote(value)}\n"
```

Or for multi-line values:
```python
script += f"export {key}={json.dumps(value)}\n"
```

---

### 2. ⚠️ Docker Volume Mount Issues (HIGH PRIORITY)
**Issue**: Line 205 - Only mounting local_stores_path, missing other critical paths

**Problem**:
- ZenML code repository not mounted
- Step code not accessible in container
- Custom artifact stores not mounted

**Fix**: Need to mount:
```python
script += f"  -v {local_stores_path}:{local_stores_path} \\\n"
script += f"  -v $(pwd):$(pwd) \\\n"  # Current directory
script += f"  -w $(pwd) \\\n"  # Working directory
```

Or use stack's `prepare_or_run_pipeline` for proper volume handling.

---

### 3. ⚠️ Job ID Extraction Fragility (MEDIUM PRIORITY)
**Issue**: Line 378
```python
job_id = result.stdout.strip().split()[-1]
```

**Problem**:
- Assumes `sbatch` output format is always "Submitted batch job 12345"
- Different SLURM versions might have different output
- No validation that extracted ID is actually numeric

**Fix**:
```python
import re
match = re.search(r'Submitted batch job (\d+)', result.stdout)
if match:
    job_id = match.group(1)
else:
    raise RuntimeError(f"Could not parse job ID from sbatch output: {result.stdout}")
```

---

### 4. ⚠️ Docker Run Arguments Not Supported (MEDIUM PRIORITY)
**Issue**: Missing docker run customization

**Problem**:
- Can't pass `docker run` flags (e.g., `--gpus`, `--ulimit`, `--cap-add`)
- Limited to basic environment and volume mounting
- No way to customize Docker behavior per-step

**Fix**: Add to SlurmOrchestratorSettings:
```python
docker_run_args: Dict[str, Any] = {}  # e.g., {"gpus": "all", "privileged": True}
```

Then in script generation:
```python
for key, value in settings.docker_run_args.items():
    if isinstance(value, bool):
        if value:
            script += f"  --{key} \\\n"
    else:
        script += f"  --{key}={value} \\\n"
```

---

### 5. ⚠️ No Resource Mapping to SLURM Directives (MEDIUM PRIORITY)
**Issue**: Lines 306-313 - Resources are logged but not applied

**Problem**:
```python
if self.requires_resources_in_orchestration_environment(step):
    resources = step.config.resource_settings
    logger.info("Step %s has resource requirements: %s", step_name, resources)
    # But then... nothing happens with resources!
```

**Fix**: Map resources to SLURM directives:
```python
if self.requires_resources_in_orchestration_environment(step):
    resources = step.config.resource_settings
    if resources.cpu_count:
        sbatch_args["cpus-per-task"] = resources.cpu_count
    if resources.memory:
        sbatch_args["mem"] = resources.memory
    if resources.gpu:
        sbatch_args["gpus"] = resources.gpu
```

---

### 6. ⚠️ Synchronous Wait Logic (MEDIUM PRIORITY)
**Issue**: Lines 396-414 - squeue polling could fail silently

**Problem**:
```python
while submitted_jobs:
    try:
        squeue_cmd = ["squeue", "-j", ",".join(submitted_jobs.values())]
        # If job failed, squeue won't show it but we won't know WHY
```

**Improvement**:
```python
def _wait_for_completion(self) -> None:
    """Wait for all submitted jobs to complete and check their exit status."""
    logger.info("Waiting for SLURM jobs to complete...")

    while submitted_jobs:
        result = subprocess.run(
            ["squeue", "-j", ",".join(submitted_jobs.values())],
            capture_output=True,
            text=True,
        )

        if len(result.stdout.strip().split("\n")) <= 1:
            # All jobs done, now check exit codes
            for step_name, job_id in submitted_jobs.items():
                exit_code_result = subprocess.run(
                    ["sacct", "-j", job_id, "--format=ExitCode"],
                    capture_output=True,
                    text=True,
                )
                # Parse and check exit codes
            break

        time.sleep(5)
```

---

### 7. ⚠️ No Error Handling for sbatch Availability (LOW PRIORITY)
**Issue**: If `sbatch` is not found, error message isn't helpful

**Fix**: Add upfront check:
```python
try:
    subprocess.run(["sbatch", "--version"], capture_output=True, check=True)
except FileNotFoundError:
    raise RuntimeError(
        "sbatch command not found. Ensure you're running from a SLURM cluster "
        "login node and SLURM is installed."
    )
```

---

### 8. ⚠️ Script Path Collision Risk (LOW PRIORITY)
**Issue**: Line 343-346

**Problem**: If two pipelines run simultaneously with same run_id (unlikely but possible), scripts overwrite

**Fix**:
```python
import tempfile
script_dir = tempfile.mkdtemp(prefix="zenml_slurm_")
script_path = os.path.join(script_dir, f"{step_name}.sh")
```

Or use UUID in filename twice:
```python
script_path = os.path.join(
    settings.output_dir or "/tmp",
    f"zenml_slurm_{orchestrator_run_id}_{step_name}_{uuid4()}.sh",
)
```

---

### 9. ⚠️ No Support for Remote Submission (LOW PRIORITY)
**Issue**: Must run from login node with `sbatch` in PATH

**Consideration**: Could add SSH support for remote orchestration from local machine, but this is beyond scope.

---

### 10. ⚠️ No Job Cancellation on Failure (LOW PRIORITY)
**Issue**: If pipeline fails, submitted jobs keep running

**Fix**: Implement cleanup in exception handlers:
```python
def _cancel_submitted_jobs(self, submitted_jobs: Dict[str, str]) -> None:
    """Cancel all submitted SLURM jobs."""
    for step_name, job_id in submitted_jobs.items():
        try:
            subprocess.run(["scancel", job_id], check=False)
            logger.info(f"Cancelled job {job_id} for step {step_name}")
        except Exception as e:
            logger.warning(f"Failed to cancel job {job_id}: {e}")
```

---

## Code Quality Improvements

### 11. Missing Logging Context (LOW PRIORITY)
**Suggestion**: Add more detailed logging for debugging
```python
logger.debug(f"Generated SLURM script:\n{script}")
logger.debug(f"Script saved to: {script_path}")
```

---

### 12. No Type Hints for Dict Values (LOW PRIORITY)
**Suggestion**: Be more specific with Dict types
```python
# Instead of:
sbatch_args: Dict[str, Any] = {}

# Use:
from typing import Union
sbatch_args: Dict[str, Union[str, int, bool]] = {}
```

---

## Documentation Gaps

### 13. Missing Examples
- Per-step GPU configuration
- Custom sbatch arguments
- Multi-GPU setup
- Large memory requirements

### 14. Missing Diagrams
- Job dependency chain visualization
- Execution flow diagram
- SLURM architecture integration

---

## Summary of Fixes by Priority

**🔴 CRITICAL** (Fix before production):
1. Environment variable escaping
2. Docker volume mounts for code
3. Job ID extraction robustness
4. Resource mapping to SLURM

**🟡 IMPORTANT** (Fix soon):
5. Docker run arguments support
6. Job exit code checking
7. sbatch availability check

**🟢 NICE-TO-HAVE** (Future improvements):
8. Script collision avoidance
9. Job cancellation on failure
10. Better logging

---

## Recommended Implementation Order

1. **First**: Fix environment variable escaping (line 193)
2. **Second**: Add proper volume mounts for Docker (line 205)
3. **Third**: Fix job ID extraction with regex (line 378)
4. **Fourth**: Map resource settings to SLURM directives (lines 306-313)
5. **Fifth**: Add docker run args support
6. **Sixth**: Enhance synchronous wait logic

These fixes would make the orchestrator production-ready.
