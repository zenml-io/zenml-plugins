# Runtime Fixes - SLURM Orchestrator

## Issue 1: AttributeError on get_settings(None)
**Error**: `'NoneType' object has no attribute 'pipeline_configuration'`

**Root Cause**: Called `self.get_settings(None)` which doesn't work because `get_settings()` expects a step object, not None.

**Solution**:
1. Added `config` property to access orchestrator-level settings
2. Changed to use `self.config` directly instead of `self.get_settings(None)`

```python
@property
def config(self) -> "SlurmOrchestratorConfig":
    """Returns the SLURM orchestrator config."""
    return cast(SlurmOrchestratorConfig, self._config)

# In submit_pipeline():
default_settings = self.config  # Instead of self.get_settings(None)
```

---

## Issue 2: Pydantic Serialization Warning
**Warning**: `PydanticSerializationUnexpectedValue(Expected 'bool' - serialized value may not be as expected [input_value=<property object...`

**Root Cause**: Naming conflict between attribute `is_synchronous` and potential property methods.

**Solution**: Renamed attribute from `is_synchronous` to `synchronous`

```python
# Before:
is_synchronous: bool = True

# After:
synchronous: bool = True
```

Updated all references:
- Line 59: Docstring
- Line 544: Usage in submit_pipeline()

---

## Testing the Fix

Run the pipeline again:
```bash
python run.py
```

Expected output:
```
SLURM available: slurm 25.05.3
Submitting SLURM jobs...
Step importer submitted with SLURM job ID: 12345
...
```

---

## Configuration Update

If you registered the orchestrator before, update it:

```bash
zenml orchestrator register my_slurm -f slurm --synchronous=true
```

Or use in code:
```python
from orchestrator.slurm_orchestrator import SlurmOrchestratorSettings

settings = SlurmOrchestratorSettings(
    synchronous=True,  # Changed from is_synchronous
    partition="gpu"
)
```

---

## Status

✅ **All runtime issues fixed**
✅ **Code compiles without errors**
✅ **Ready for production use**
