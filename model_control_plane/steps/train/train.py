import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from typing_extensions import Annotated
from zenml import log_artifact_metadata, step
from zenml.model import ModelArtifactConfig


@step
def train_and_evaluate(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> Annotated[
    ClassifierMixin, "iris_classifier", ModelArtifactConfig()
]:  # it will be linked as model object
    """Runs training and evaluation combined.

    This is due to current limitation of `log_artifact_metadata`, which
    can only log metadata to step outputs.
    """
    classifier = LogisticRegression()
    classifier.fit(train_data.drop(columns=["target"]), train_data["target"])

    predictions = classifier.predict(test_data.drop(columns=["target"]))
    score = accuracy_score(predictions, test_data["target"])
    log_artifact_metadata(output_name="iris_classifier", accuracy=score)
    return classifier
