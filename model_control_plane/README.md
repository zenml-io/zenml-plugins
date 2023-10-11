# Model Control Plane backend walkthrough

## Structure

In this example we are working with a `demo` Model, which is created using Python SDK implicitly.
We have two pipelines:

- Producer pipeline is doing training of a model object and stores datasets and model object itself as link inside newly created Model Version. As a last step of the pipeline we promote this new Model Version to Production stage. We achieve this by setting pipeline into Model Context using `ModelConfig` with specified `name` and `create_new_model_version`, rest of the fields are optional for this task.
```python
from zenml import pipeline
from zenml.model import ModelConfig

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
    ...
```
- Consumer pipeline is reading trained model object from the Model Version tagged as Production to produce predictions and link them also to the same Model Version. As predictions pipeline can run more often comparing to training pipeline, we will link predictions as a versioned artifact, so we can see full history later on. We achieve this by setting pipeline into Model Context using `ModelConfig` with specified `name` and `version`. Version can be also represented by version number (`1` or `"1"` in our case) or name (`demo` in our case).
```python
from zenml import pipeline
from zenml.model import ModelConfig

@pipeline(
    enable_cache=False,
    model_config=ModelConfig(
        name="demo",
        version=ModelStages.PRODUCTION,
    ),
)
def consumer():
    ...
```

## Try it yourself
### Run training
```bash
# clean up state before start [Optional]
zenml clean

# install needed integrations
zenml integration install sklearn

# verify existing models (if clean executed - should be empty)
zenml model list

# run training pipeline: it will create a model, a model version and link
# two datasets and one model object to it.
# pipeline run is linked automatically.
python3 train.py

# new model `demo` created
zenml model list

# new model version `1` created
zenml model version list demo

# list dataset artifacts - train and test are here
zenml model version artifacts demo 1

# list model objects - trained classifier here
zenml model version model_objects demo 1

# list deployments - none
zenml model version deployments demo 1

# list runs - only training run linked
zenml model version runs demo 1
```
### Run predictions
```bash
# run prediction pipeline: it will use Production staged Model Version to read Model Object and
# produce predictions as versioned artifact link
python3 predict.py

# no new model version created, just consuming existing model
zenml model version list demo

# list dataset and predictions artifacts
zenml model version artifacts demo 1

# run prediction pipeline again: it will use same Model Version again and
# link new predictions version link
python3 predict.py

# list dataset and predictions (2 versions now) artifacts
zenml model version artifacts demo 1

# list runs, prediction runs are also here
zenml model version runs demo 1
```
### Update existing model via CLI
```bash
zenml model update demo -t tag1 -t tag2 -e "some ethical implications"
```
### Create a model via CLI
```bash
zenml model register -n demo_cli -d "created from cli" -t cli
```
### Clean up
```bash
zenml model delete demo_cli
zenml model delete demo -y
```