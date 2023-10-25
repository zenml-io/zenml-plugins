from zenml import get_step_context, step
from zenml.enums import ModelStages
from zenml.logger import get_logger

logger = get_logger(__name__)


@step
def promote_to_staging(score: float):
    logger.info(f"The latest model score is: {score}")
    if score > 0.7:
        logger.info("Passed quality control... Promoting.")
        model_config = get_step_context().model_config
        model_version = model_config._get_model_version()
        model_version.set_stage(ModelStages.STAGING, force=True)
    else:
        logger.info("Latest model failed quality control. Not promoting.")
