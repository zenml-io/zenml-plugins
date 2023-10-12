from zenml import get_step_context, step
from zenml.enums import ModelStages


@step
def promote_to_staging():
    model_config = get_step_context().model_config
    model_version = model_config._get_model_version()
    model_version.set_stage(ModelStages.STAGING, force=True)
