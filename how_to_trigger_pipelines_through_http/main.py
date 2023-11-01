import os
import tempfile
import subprocess
import functions_framework

import yaml
from flask import abort

PIPELINE_NAME = os.getenv('PIPELINE_NAME')
PIPELINE_BUILD = os.getenv('PIPELINE_BUILD')
ZENML_STACK = os.getenv('ZENML_STACK')
ZENML_SERVER_URL = os.getenv('ZENML_SERVER_URL')
ZENML_USERNAME = os.getenv('ZENML_USERNAME')
ZENML_PASSWORD = os.getenv('ZENML_PASSWORD')


def process_data(data) -> str:
    yaml_file = os.path.join(tempfile.gettempdir(), "config.yaml")
    # write to yaml
    with open(yaml_file, 'w') as file:
        yaml.dump(data, file)

    return yaml_file


@functions_framework.http
def zenml_trigger_pipeline(request):
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            config_file = process_data(data)

            try:
                subprocess.run(
                    ["zenml", "connect", "--url", ZENML_SERVER_URL,
                     "--username", ZENML_USERNAME, "--password", ZENML_PASSWORD]
                )
                subprocess.run(
                    ["zenml", "pipeline", "run", "-c", config_file,
                     "-s", ZENML_STACK, "-b", PIPELINE_BUILD, PIPELINE_NAME]
                )
            finally:
                os.remove(config_file)
                return 'Success', 200
        else:
            return 'Invalid JSON request', 400
    else:
        return abort(405)
