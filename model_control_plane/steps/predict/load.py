from typing import Tuple

import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from typing_extensions import Annotated
from zenml import step


@step
def load_data() -> (
    Annotated[pd.DataFrame, "inference_data"]
):  # it will be linked implicitly
    iris = load_iris()
    data = pd.DataFrame(iris.data, columns=iris.feature_names)
    _, test_data = train_test_split(data, test_size=0.2)
    return test_data
