from typing import Annotated

import pandas as pd
from sklearn.base import ClassifierMixin
from zenml import step
from zenml.model.artifact_config import ArtifactConfig


@step
def predict(
    model: ClassifierMixin,
) -> Annotated[
    pd.Series,
    "predictions",
    ArtifactConfig(artifact_name="iris_predictions", overwrite=False),
]:
    inference_data = pd.DataFrame(
        [
            {
                "sepal length (cm)": 5.1,
                "sepal width (cm)": 3.5,
                "petal length (cm)": 1.4,
                "petal width (cm)": 0.2,
            }
        ]
    )
    predictions = pd.Series(model.predict(inference_data))
    return predictions
