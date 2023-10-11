# Model Control Plane backend walkthrough

In this example, we are working with two pipelines, which are independent entities in ZenML. Those pipelines produce artifacts connected to them. But these two pipelines and their artifacts are actually connected! They all work towards delivering predictions to users.

Before the Model Control Plane, it was not possible to establish strong connections between them and group all those entities under one umbrella. Imagine how you would get a trained model artifact from the training pipeline inside the predictions pipeline: you can reference it by ID (meaning frequent updates to your config) or blindly rely on the latest run of the training pipeline. What if the last training run was successful, but didn't fulfill business requirements model metric performance-wise? Your predictions will be based on the poor-performing model, which is unacceptable for critical applications!

With the Model Control Plane, we finally get the ability to nicely and intuitively group pipelines, artifacts, and business-relevant metadata into one business-focused object - a Model. A Model will build all the linage info for you and not only! Within a Model a Model Version can be staged, so you can rely on your predictions pipeline at some stage (say Staging in this example) and control if the Model Version should be promoted or not based on your business logic (here we promote the latest, but this is not a limit). All the objects collected inside a Model Version are easily and without config duplications accessible to your pipelines at any time and even more - you can access data from other Models and their Model Versions with the same ease.

Stay tuned for more features to come (*current state of planning*)

- Modern Cloud UI to make navigation through all your Models even easier
- Ability to save artifacts inside he steps and restore from that point on failure, which comes in handy for model checkpoints and more
- Ability to attach metadata to artifacts linked to a Model Version outside of the step creating it (e.g. train and evaluation steps split)
- Generation of Model Cards using ZenML delivered or your own templates and based on all linage information collected
- Automatic registration of Model Objects in Model Registry instead of Artifact Store of ZenML

and more!

## Structure

In this example we are working with a `demo` Model, which is created using Python SDK implicitly.
We have two pipelines:

**Training pipeline** is doing training of a model object and stores datasets and model object itself as link inside newly created Model Version. As a last step of the pipeline we promote this new Model Version to Staging stage. We achieve this by setting pipeline into Model Context using `ModelConfig` with specified `name` and `create_new_model_version`, rest of the fields are optional for this task.
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
**Predictions pipeline** is reading trained model object from the Model Version tagged as Staging to produce predictions and link them also to the same Model Version. As predictions pipeline can run more often comparing to training pipeline, we will link predictions as a versioned artifact, so we can see full history later on. We achieve this by setting pipeline into Model Context using `ModelConfig` with specified `name` and `version`. Version can be also represented by version number (`1` or `"1"` in our case) or name (`demo` in our case).
```python
from zenml import pipeline
from zenml.model import ModelConfig

@pipeline(
    enable_cache=False,
    model_config=ModelConfig(
        name="demo",
        version=ModelStages.STAGING,
    ),
)
def consumer():
    ...
```

Inside predictions pipeline we also pass previously linked artifact from training stage using Model Context. To achieve this `ExternalArtifact` is used and we also pass artifact name as pipeline configuration extra.

Since we configured Model Context on pipeline level it is not needed to repeat it again in `ExternalArtifact`, but you can also pull artifacts from outside of Model Context using `model_name` and `model_version` attributes of `ExternalArtifact`.

We also can pass and read any extra configuration required using `extra` pipeline argument and new `get_pipeline_context` function.
```python
from zenml import pipeline, get_pipeline_context
from zenml.artifacts.external_artifact import ExternalArtifact

@pipeline(
    model_config=...,
    extra={"trained_classifier": "iris_classifier"},
)
def do_predictions():
    ...
    predict(
        model=ExternalArtifact(
            model_artifact_name=get_pipeline_context().extra["trained_classifier"]
        ),  # model_name and model_version derived from pipeline context
        ...
    )
    ...
```

## Try it yourself
### Run training
```bash
# clean up state before start [Optional]
zenml clean

# install needed integrations
zenml integration install sklearn

# verify existing models (if `zenml clean` executed - should be empty)
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

# list train, test and inference datasets and predictions artifacts
zenml model version artifacts demo 1

# run prediction pipeline again: it will use same Model Version again and
# link new predictions version link
python3 predict.py

# list train, test datasets and two version of inference dataset and prediction artifacts
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