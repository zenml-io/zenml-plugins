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
cd zenml-plugins/how_to_custom_orchestrator

# install the necessary dependencies
pip install -r requirements.txt
```

### 🚀 Registering the Custom Orchestrator

First, you need to register the flavor of the orchestrator:

```shell
# register the flavor of the orchestrator
zenml orchestrator flavor register orchestrator.my_docker_orchestrator.MyDockerOrchestratorFlavor 
```

Then, you register your custom orchestrator using your registered flavor:

```shell
# register the custom orchestrator
zenml orchestrator register my_docker_orchestrator -f my_docker  
```

### 📝 Registering and Setting the Stack

Next, you need to register a stack with your custom orchestrator and the default artifact store attached:

```shell
# register the stack
zenml stack register my_stack -o my_docker_orchestrator -a default
```

Finally, set the stack active. This means every pipeline that runs will use the custom orchestrator:

```shell
# set the stack active
zenml stack set my_stack
```

## 📚 Learn More

For more information on creating a custom orchestrator in ZenML, follow this [guide](https://docs.zenml.io/stacks-and-components/component-guide/orchestrators).