from zenml import pipeline, get_pipeline_context
from zenml.artifacts.external_artifact import ExternalArtifact
from zenml.enums import ModelStages
from zenml.model import ModelConfig

from steps.predict.load import load_data
from steps.predict.predict import predict


@pipeline(
    enable_cache=False,
    model_config=ModelConfig(
        name="demo",
        version=ModelStages.STAGING,
    ),
    extra={"trained_classifier": "iris_classifier"},
)
def do_predictions():
    inference_data = load_data()
    predict(
        model=ExternalArtifact(
            model_artifact_name=get_pipeline_context().extra["trained_classifier"]
        ),  # model_name and model_version derived from pipeline context
        data=inference_data,
    )


if __name__ == "__main__":
    do_predictions()
