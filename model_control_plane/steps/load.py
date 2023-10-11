from typing import Tuple

import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from typing_extensions import Annotated
from zenml import step
from zenml.model import ArtifactConfig, link_output_to_model


@step
def load_data() -> (
    Tuple[
        Annotated[pd.DataFrame, "train_data"],
        Annotated[pd.DataFrame, "test_data"],
    ]
):
    link_output_to_model(ArtifactConfig(overwrite=True), output_name="train_data")
    iris = load_iris()
    data = pd.concat(
        [
            pd.DataFrame(iris.data, columns=iris.feature_names),
            pd.Series(iris.target, name="target"),
        ],
        axis=1,
    )
    train_data, test_data = train_test_split(data, test_size=0.2)
    return train_data, test_data
