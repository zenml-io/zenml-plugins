# How to trigger a ZenML pipeline remotely with custom configuration

## Setup on the GCP side

1) Choose a GCP project

2) [Enable these APIs](https://console.cloud.google.com/flows/enableapi?apiid=cloudfunctions,cloudbuild.googleapis.com,artifactregistry.googleapis.com,run.googleapis.com,logging.googleapis.com&redirect=https://cloud.google.com/functions/docs/create-deploy-gcloud&_ga=2.103703808.1862683951.1694002459-205697788.1651483076&_gac=1.161946062.1694011263.Cj0KCQjwxuCnBhDLARIsAB-cq1ouJZlVKAVPMsXnYrgQVF2t1Q2hUjgiHVpHXi2N0NlJvG3j3y-PPh8aAoSIEALw_wcB)
* Cloud Build
* Cloud Functions
* Artifact Registry
* Cloud Run
* Logging

3) Connect to GCP and choose the project
```bash
gcloud auth login
gcloud config set project <PROJECT_ID>
```

## Setup on the ZenML Side

1) Configure or Set your remote stack

_You will need to run with a remote orchestrator, container registry and
artifact store for this to work._

2) Run your pipeline once from a developer machine while connected to your ZenML Server
```bash
python zenml_pipeline.py
```

## Deploy the Cloud Function

1) Whenever you have code changes to a pipeline that you already ran once,
you can now also simply rebuild the pipeline without actually running it:
```bash
zenml pipeline build <PIPELINE_NAME>
```

Simply copy the build id from the logs.

2) Deploy the pipeline_trigger to GCP CLoud Functions

Make sure, the complete pipeline code including all dependencies is in the same
folder as the main.py, along with a requirements.txt file that includes **all
requirements of the pipeline and the stack**. 

The following values you will need to pass in as env vars:
* PIPELINE_NAME  # This will be the function name of the ZenML pipeline
* PIPELINE_BUILD  # This is where the build id goes
* ZENML_STACK  # This needs to be the stack that the pipeline was run on/ built on
* ZENML_SERVER_URL  # This needs to be the same server that the pipeline was run with
* ZENML_USERNAME
* ZENML_PASSWORD  # For production use it might be recommended to find a way to load this from a secret manager

```bash
cd deployment
gcloud functions deploy zenml_trigger_pipeline \
--gen2 --runtime python310 --trigger-http --allow-unauthenticated \
--region europe-central2 --memory=512mib \
--set-env-vars ZENML_PASSWORD=<INSERT-HERE>,ZENML_USERNAME=<INSERT-HERE>,ZENML_SERVER_URL=<INSERT-HERE>,PIPELINE_NAME=<INSERT-HERE>,PIPELINE_BUILD=<INSERT-HERE>,ZENML_STACK=<INSERT-HERE>  
```

_For large python packages within the requirements file, you might need to 
increase the `--memory` of this function._

3) You may now trigger your pipeline on the endpoint provided by the 
GCloud function.

```bash
curl --location '<INSERT-URL-HERE' \
--header 'Content-Type: application/json' \
--data '{
    "steps": {
        "svc_trainer": {
            "parameters": {
                "gamma": 0.01
            }
        }
    }
}'
```

## Hints

1) To understand how your pipeline can be configured, simply go into your code, 
find the pipeline instance and do this:

```python
first_pipeline.write_run_configuration_template("filepath.yaml")
```

Convert this yaml into a json and you have a template for the json that you can
post to the endpoint.

2) When you make changes to your code, you will need to:

* Rebuild the pipeline
* Redeploy the gcloud function with the new build id