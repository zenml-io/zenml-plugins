from zenml import pipeline
from zenml.artifacts.external_artifact import ExternalArtifact
from zenml.enums import ModelStages
from zenml.model import ModelConfig

from steps.predict import predict


@pipeline(
    enable_cache=False,
    model_config=ModelConfig(
        name="demo",
        version=ModelStages.PRODUCTION,
    ),
)
def consumer():
    predict(ExternalArtifact(model_artifact_name="iris_classifier"))
