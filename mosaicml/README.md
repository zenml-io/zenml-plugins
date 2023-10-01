# 🎼 Create a Custom Orchestrator with ZenML

ZenML allows you to create a custom orchestrator, an essential component in any MLOps stack responsible for running your machine learning pipelines. This tutorial guides you through the process of creating an orchestrator that runs each step of a pipeline locally in a docker container.

## ❓Why would you need a custom orchestrator?

While ZenML comes built with standard integrations for well-known orchestrators like [Airflow](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/airflow), [Kubeflow](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/kubeflow), and even running [locally](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/local), your business might either want to orchestrate your ML workloads differently or slightly tweak the implementations of the standard orchestrators. In this case, this guide is useful, as it implements a relatively simple orchestrator.

## 📚 Overview

The `BaseOrchestrator` abstracts away many of the ZenML-specific details from the actual implementation and exposes a simplified interface. This example is an end-to-end guide on creating a custom orchestrator using ZenML. Click [here](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators/custom) to learn more about the custom orchestrator interface.

## 💻 Running it Locally

### 📑 Prerequisites

To run this example, you need to have ZenML installed along with the necessary dependencies. You can do so by executing the following commands:

```shell
# clone the ZenML plugin repository
git clone git@github.com:zenml-io/zenml-plugins.git

# navigate to the custom orchestrator directory
cd zenml-plugins/mosaicml

# install the necessary dependencies
pip install -r requirements.txt
```

### 🚀 Registering the Custom Orchestrator

First, you need to register the flavor of the orchestrator:

```shell
# initialize zenml
zenml init 

# register the flavor of the orchestrator
zenml orchestrator flavor register orchestrator.mosaic_orchestrator.MosaicMLOrchestrator 
```

Then, you register your custom orchestrator using your registered flavor:

```shell
# register the custom orchestrator
zenml orchestrator register mosaic_orchestrator -f mosaic  
```

### 📝 Registering and Setting the Stack

Next, you need to register a stack with your mosaic orchestrator, a [remote artifact store](https://docs.zenml.io/stacks-and-components/component-guide/artifact-stores), and a [remote container registry](https://docs.zenml.io/stacks-and-components/component-guide/container-registries).

```shell
# register a stack with the right type of components
zenml stack register mosaic_stack \
  -o mosaic_orchestrator \
  -a remote_artifact_store \
  -c remote_registry 
```

Finally, set the stack active. This means every pipeline that runs will use the custom orchestrator:

```shell
# set the stack active
zenml stack set mosaic_stack
```

## 📚 Learn More

For more information on creating a custom orchestrator in ZenML, follow this [guide](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators).