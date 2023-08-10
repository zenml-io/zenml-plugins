# 🧮 Train models on remote environments

This example shows how you can use the `StepOperator` class to run your training
jobs on remote backends.

The step operator defers the execution of individual steps in a pipeline to
specialized runtime environments that are optimized for Machine Learning
workloads.

## 🗺 Overview

Here, we train a simple sklearn classifier on the MNIST dataset using one of 
a custom step operator: The AWS Batch Step Operator

# 🖥 Run it locally

## 👣 Step-by-Step

### 📄 Prerequisites

In order to run this example, you need to install and initialize ZenML and the
necessary integrations:

```shell
# install CLI
pip install "zenml[server]"

# install ZenML integrations
zenml integration install sklearn

# pull example
zenml example pull step_operator_remote_training
cd zenml_examples/step_operator_remote_training

# initialize
zenml init
```

Additionally, you require a remote ZenML server deployed to the cloud. See the 
[deployment guide](https://docs.zenml.io/platform-guide/set-up-your-mlops-platform/deploy-zenml) for
more information.

Each type of step operator has their own prerequisites.

Before running this example, you must set up the individual cloud providers in a
certain way. The complete guide can be found in
the [docs](https://docs.zenml.io/user-guide/component-guide/step-operators/step-operators).

Please jump to the section applicable to the step operator you would like to 
use:


### ▶️ Run the Code

Now we're ready. Execute:

```shell
python run.py
```

### 🧽 Clean up

To destroy any resources deployed using the ZenML `deploy` subcommand, use the
`destroy` subcommand to delete each individual stack component, as in the
following example:

```shell
# replace with the name of the component you want to destroy
zenml artifact-store destroy s3_artifact_store
```

Then delete the remaining ZenML references:

```shell
rm -rf zenml_examples
```

# 📜 Learn more

Our docs for the step operator integrations can be
found [here](https://docs.zenml.io/user-guide/component-guide/step-operators/step-operators).

If you want to learn more about step operators in general or about how to build
your own step operator in ZenML
check out our [docs](https://docs.zenml.io/user-guide/component-guide/step-operators/custom).
