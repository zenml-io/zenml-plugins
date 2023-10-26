from zenml import pipeline
from zenml.model import ModelConfig

from steps.train.load import load_data
from steps.train.promote import promote_model
from steps.train.train import train_and_evaluate


@pipeline(
    enable_cache=False,
    model_config=ModelConfig(
        name="demo",
        license="Apache",
        description="Show case Model Control Plane.",
        create_new_model_version=True,
        delete_new_version_on_failure=True,
    ),
)
def train_and_promote_model():
    train_data, test_data = load_data()
    model, score = train_and_evaluate(train_data=train_data, test_data=test_data)
    promote_model(score=score)


if __name__ == "__main__":
    train_and_promote_model()
