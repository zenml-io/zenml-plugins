from zenml import get_step_context, step
from zenml.enums import ModelStages


@step
def promote():
    model_config = get_step_context().model_config
    model_version = model_config.get_or_create_model_version()
    model_version.set_stage(ModelStages.PRODUCTION, force=True)
