from zenml import pipeline
from zenml.model import ModelConfig

from steps.load import load_data
from steps.promote import promote
from steps.train import train


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
def producer():
    train_data, test_data = load_data()
    train(train_data)
    promote(after=["train"])
