#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Example steps for SLURM orchestrator demonstration."""

from typing import Annotated

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from zenml import step
from zenml.config import ResourceSettings
from orchestrator.slurm_orchestrator import SlurmOrchestratorSettings

@step(
    settings={
        "resources": ResourceSettings(
            cpu_count=4,
            memory="8GB",
        )
    }
)
def importer() -> Annotated[pd.DataFrame, "data"]:
    """Loads the Iris dataset."""
    iris = load_iris()
    return pd.DataFrame(
        iris.data,
        columns=[
            "sepal_length",
            "sepal_width",
            "petal_length",
            "petal_width"
        ]
    )


@step(
    settings={
        "orchestrator.slurm": SlurmOrchestratorSettings(
            partition="compute",     # Use specific partition
            sbatch_args={
                "exclusive": True,   # Get exclusive node access
            }
        )
    }
)
def splitter(
    data: pd.DataFrame,
) -> tuple[
    Annotated[pd.DataFrame, "X_train"],
    Annotated[pd.DataFrame, "X_test"],
    Annotated[np.ndarray, "y_train"],
    Annotated[np.ndarray, "y_test"],
]:
    """Splits the dataset into train and test sets."""
    iris = load_iris()
    y = iris.target

    X_train, X_test, y_train, y_test = train_test_split(
        data, y, test_size=0.2, random_state=42
    )

    return X_train, X_test, y_train, y_test


@step
def trainer(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
) -> Annotated[RandomForestClassifier, "model"]:
    """Trains a Random Forest classifier."""
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model


@step
def evaluator(
    model: RandomForestClassifier,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
) -> Annotated[float, "accuracy"]:
    """Evaluates the model on the test set."""
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    return accuracy
