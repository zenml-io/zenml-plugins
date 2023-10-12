# Navigating the Model Control Plane Backend: A Guided Tour

In this walkthrough, we delve into the intricacies of the Model Control Plane, focusing on two distinct but interrelated pipelines within ZenML. Each pipeline operates independently within the ZenML framework, producing artifacts tailored to its specific tasks. What makes this exploration fascinating is the realization that these seemingly isolated pipelines are, in fact, intricately connected. Their joint objective? Delivering accurate predictions to end-users.

Before the advent of the Model Control Plane, establishing robust connections between these pipelines and consolidating all associated entities under a unified umbrella was a challenge. Picture this: extracting a trained model artifact from the training pipeline and seamlessly integrating it into the predictions pipeline. Previously, this involved referencing it by ID, leading to frequent updates to configurations, or relying blindly on the latest run of the training pipeline. But what if the last training run, though successful, fell short of the business requirements concerning model metric performance? Deploying predictions based on a subpar model was simply unacceptable, especially for critical applications!

Enter the Model Control Plane. This innovative feature empowers users to effortlessly group pipelines, artifacts, and business-relevant metadata into a cohesive and intuitive entity: a Model. A Model meticulously captures lineage information and more. Within a Model, various Model Versions can be staged. For instance, you can depend on your predictions pipeline at a specific stage, such as the Staging phase, and exercise control over whether the Model Version should be promoted based on your business logic (although promoting the latest version is a common practice, it's not a strict limitation). Moreover, all the components housed within a Model Version are readily accessible to your pipelines without the need for redundant configurations. Additionally, accessing data from other Models and their Model Versions is just as effortless, amplifying the platform's flexibility.

## Illustrative Example

To illustrate these concepts, let's consider a `demo` Model will be created implicitly using the Python SDK.

### Preparatory Steps
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
The Training pipeline orchestrates the training of a model object, storing datasets and the model object itself as links within a newly created Model Version. This integration is achieved by configuring the pipeline within a Model Context using `ModelConfig`. The `name` and `create_new_model_version` fields are specified, while other fields remain optional for this task.
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
In the final step of the pipeline, the new Model Version is promoted to the Staging stage.
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

Executing the training pipeline results in the creation of a model and a corresponding model version, all while maintaining lineage for the associated artifacts.
```bash
# run training pipeline: it will create a model, a 
# model version and link two datasets and one model 
# object to it, pipeline run is linked automatically
python3 train.py
```
Upon successful completion, explore the results to gain insights into the newly created entities:
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
The Predictions pipeline reads the trained model object from the Model Version tagged as Staging, generating predictions and linking them to the same Model Version. The `version` is set to a stage value, ensuring that the pipeline uses the Model Version in the Staging stage for every run. This approach makes the pipeline independent of the underlying logic of promotion in the Training pipeline.
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
Given that the predictions pipeline can run more frequently than the training pipeline, predictions are linked as versioned artifacts. This is controlled by the `overwrite` flag in the artifact configuration.
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
In this setup, model versions can also be represented by version numbers or names, providing additional flexibility.

### Artifact Exchange Between Pipelines Using Model Context

Within the predictions pipeline, artifacts linked in the training stage are passed on. This is accomplished using `ExternalArtifact`. Given that the model name and version are already set at the pipeline level, there's no need to repeat this information.

*Handy Tip*: It's worth noting that artifacts from other models can also be fetched using the `model_name` and `model_version` attributes of `ExternalArtifact`.

```python
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
Moreover, any additional configurations required can be effortlessly passed and accessed using the `extra` pipeline argument and the newly introduced `get_pipeline_context` function.
```python
@pipeline(
    extra={"trained_classifier": "iris_classifier"},
)
def do_predictions():
    trained_classifier = get_pipeline_context().extra["trained_classifier"]
    ...
```

Upon execution of the prediction pipeline, the Production-staged Model Version is utilized to read the Model Object and generate predictions, which are then linked as versioned artifact references.
```bash
# run prediction pipeline: it will use Production 
# staged Model Version to read Model Object and 
# produce predictions as versioned artifact link
python3 predict.py

# no new model version created, just consuming existing model
zenml model version list demo

# list train, test and inference datasets and predictions artifacts
zenml model version artifacts demo 1
```
Marvelously, the Staging-staged model version is seamlessly reused, with both the inference dataset and predictions attached to it. This unified approach ensures a hassle-free traceability of predictions back to their training data and model metrics, fostering a comprehensive understanding of the entire process.

It's essential to remember that artifacts generated in the prediction pipeline are versioned. What happens if we rerun the pipeline?
```bash
# run prediction pipeline again: it will use same 
# Model Version again and link new predictions version link
python3 predict.py

# list train, test datasets and two version of 
# inference dataset and prediction artifacts
zenml model version artifacts demo 1

# list runs, prediction runs are also here
zenml model version runs demo 1
```
Everything proceeds as anticipated! Two additional links have been appended to our artifacts, representing new versions of predictions and inference dataset. This nuanced approach allows for in-depth analysis or the retrieval of predictions from specific dates, offering enhanced flexibility. Moreover, the prediction pipeline runs are conveniently tied to the same model version, providing a clear understanding of the code that interacts with your models.

### Bringing Everything Together in Harmony
Now, let's tie all the threads together in a seamless flow.
<p align="center">
  <img src="img/train_prediction_example.png">
</p>

### Additional CLI Features
#### Updating Existing Models via CLI
```bash
zenml model update demo -t tag1 -t tag2 -e "some ethical implications"
```
#### Creating a Model via CLI
```bash
zenml model register -n demo_cli -d "created from cli" -t cli
```

### Excellent work! Let's tidy up a bit.
```bash
zenml model delete demo_cli
zenml model delete demo -y
```