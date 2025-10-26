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
"""Example pipeline for SLURM orchestrator demonstration."""

from zenml import pipeline
from steps.example_steps import importer, splitter, trainer, evaluator


@pipeline
def ml_pipeline():
    """Simple ML pipeline for Iris dataset classification."""
    data = importer()
    X_train, X_test, y_train, y_test = splitter(data)
    model = trainer(X_train, y_train)
    accuracy = evaluator(model, X_test, y_test)
    return accuracy
