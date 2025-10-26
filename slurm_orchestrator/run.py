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
"""Run script for the SLURM orchestrator example."""

import logging
import sys

from pipelines.example_pipeline import ml_pipeline

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Execute the ML pipeline."""
    logger.info("Starting ML pipeline execution...")

    try:
        # Run the pipeline
        result = ml_pipeline()
        logger.info("Pipeline execution completed successfully!")
        logger.info("Pipeline result: %s", result)
        return 0
    except Exception as e:
        logger.error("Pipeline execution failed: %s", str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
