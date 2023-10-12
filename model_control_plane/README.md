# Model Control Plane backend walkthrough

In this example, we are working with two pipelines, which are independent entities in ZenML. Those pipelines produce artifacts connected to them. But these two pipelines and their artifacts are actually connected! They all work towards delivering predictions to users.

Before the Model Control Plane, it was not possible to establish strong connections between them and group all those entities under one umbrella. Imagine how you would get a trained model artifact from the training pipeline inside the predictions pipeline: you can reference it by ID (meaning frequent updates to your config) or blindly rely on the latest run of the training pipeline. What if the last training run was successful, but didn't fulfill business requirements model metric performance-wise? Your predictions will be based on the poor-performing model, which is unacceptable for critical applications!

With the Model Control Plane, we finally get the ability to nicely and intuitively group pipelines, artifacts, and business-relevant metadata into one business-focused object - a Model. A Model will build all the linage info for you and not only! Within a Model a Model Version can be staged, so you can rely on your predictions pipeline at some stage (say Staging in this example) and control if the Model Version should be promoted or not based on your business logic (here we promote the latest, but this is not a limit). All the objects collected inside a Model Version are easily and without config duplications accessible to your pipelines at any time and even more - you can access data from other Models and their Model Versions with the same ease.

## Example

In this example we are working with a `demo` Model, which is created using Python SDK implicitly.

### Preparations
```bash
# make sure you have ZenML of 0.45.0 or above installed
pip3 install "zenml[dev]>=0.45.0"

# [Optional] clean up state before start 
zenml clean

# install needed integrations
zenml integration install sklearn

# verify existing models (if `zenml clean` executed - should be empty)
zenml model list
```

### Training pipeline
**Training pipeline** is doing training of a model object and stores datasets and model object itself as link inside newly created Model Version. We achieve this by setting pipeline into Model Context using `ModelConfig` with specified `name` and `create_new_model_version`, rest of the fields are optional for this task.
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
def train_and_promote_model():
    ...
```
As a last step of the pipeline we promote this new Model Version to Staging stage.
```python
from zenml import get_step_context, step, pipeline
from zenml.enums import ModelStages

@step
def promote_to_staging():
    model_config = get_step_context().model_config
    model_version = model_config._get_model_version()
    model_version.set_stage(ModelStages.STAGING, force=True)

@pipeline(
    ...
)
def train_and_promote_model():
    ...
    promote_to_staging(after=["train_and_evaluate"])
```

Now let's run training pipeline - it will create a model and a model version under the hood. On top it will take care of linage for your artifacts along the way.
```bash
# run training pipeline: it will create a model, a model version and link two datasets and one model object to it, pipeline run is linked automatically.
python3 train.py
```
Upon successful completion let's explore the results:
```bash
# new model `demo` created
zenml model list

# new model version `1` created
zenml model version list demo

# list generic artifacts - train and test datasets are here
zenml model version artifacts demo 1

# list model objects - trained classifier here
zenml model version model_objects demo 1

# list deployments - none, as we didn't link any
zenml model version deployments demo 1

# list runs - training run linked
zenml model version runs demo 1
```

### Predictions pipeline
**Predictions pipeline** is reading trained model object from the Model Version tagged as Staging to produce predictions and link them also to the same Model Version. In this case `version` is set to a stage value, so on every run a Model Version in Staging will be used. This makes this pipeline agnostic of underlying logic of promotion in Training pipeline.
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
def do_predictions():
    ...
```
As predictions pipeline can run more often comparing to training pipeline, we will link predictions as a versioned artifact, so we can see full history later on. This is controlled by `overwrite` flag of an artifact configuration.
```python
@step
def predict(
    ...
) -> Annotated[
    pd.Series,
    "predictions",
    ArtifactConfig(artifact_name="iris_predictions", overwrite=False),
]:
    ...
```
If you would like to use model version not by stage - we got you covered and `version` can be also represented by version number or name.

### Exchange artifacts between pipelines using Model Context

Inside predictions pipeline we also pass previously linked artifact from training stage. To achieve this we use `ExternalArtifact`. Since we configured model name and model version is already set on pipeline level no need to repeat it again.

*Pro tip*: you can also pull artifacts from other models using `model_name` and `model_version` attributes of `ExternalArtifact`.

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
            model_artifact_name=trained_classifier
        ),  # model_name and model_version derived from pipeline context
        ...
    )
    ...
```
We also can pass and read any extra configuration required using `extra` pipeline argument and new `get_pipeline_context` function.
```python
@pipeline(
    extra={"trained_classifier": "iris_classifier"},
)
def do_predictions():
    trained_classifier = get_pipeline_context().extra["trained_classifier"]
    ...
```

Now we discussed the features of predictions pipeline - let's give it a shot!
```bash
# run prediction pipeline: it will use Production staged Model Version to read Model Object and produce predictions as versioned artifact link
python3 predict.py

# no new model version created, just consuming existing model
zenml model version list demo

# list train, test and inference datasets and predictions artifacts
zenml model version artifacts demo 1
```
Great! We reused model version in Staging stage and attached inference dataset and predictions to it. They all are collected under same roof of model version, so you can always back trace you predictions to training data and model metrics and more.

Remember, artifacts we create in prediction pipeline are versioned, what if we run it again?
```bash
# run prediction pipeline again: it will use same Model Version again and link new predictions version link
python3 predict.py

# list train, test datasets and two version of inference dataset and prediction artifacts
zenml model version artifacts demo 1

# list runs, prediction runs are also here
zenml model version runs demo 1
```
All worked as expected! We added two more links to our artifacts to represent new predictions and inference dataset versions, later on you can use that for analysis or to retrieve predictions from specific date, for example.
Also you can see that prediction pipeline runs are also attached to the same model version for convenience, so you always know which code interacted with your models!

### More CLI features
#### Update existing model via CLI
```bash
zenml model update demo -t tag1 -t tag2 -e "some ethical implications"
```
#### Create a model via CLI
```bash
zenml model register -n demo_cli -d "created from cli" -t cli
```

### Well done, let's clean up a bit!
```bash
zenml model delete demo_cli
zenml model delete demo -y
```