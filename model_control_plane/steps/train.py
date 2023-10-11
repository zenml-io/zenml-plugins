from typing import Annotated

import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.linear_model import LogisticRegression
from zenml import step
from zenml.model import ModelArtifactConfig


@step
def train(
    train_data: pd.DataFrame,
) -> Annotated[ClassifierMixin, "iris_classifier", ModelArtifactConfig()]:
    classifier = LogisticRegression()
    classifier.fit(train_data.drop(columns=["target"]), train_data["target"])
    return classifier
