import pandas as pd
from sklearn.base import ClassifierMixin
from typing_extensions import Annotated
from zenml import step
from zenml.model.artifact_config import ArtifactConfig


@step
def predict(
    model: ClassifierMixin,
    data: pd.DataFrame,
) -> Annotated[
    pd.Series,
    "predictions",
    ArtifactConfig(artifact_name="iris_predictions", overwrite=False),
]:
    predictions = pd.Series(model.predict(data))
    return predictions
