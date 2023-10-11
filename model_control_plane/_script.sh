zenml integration install sklearn

zenml model list

python3 train.py

zenml model list # new model `demo` created

zenml model version list demo # new model version `1` created

zenml model version artifacts demo 1 # list dataset artifacts

zenml model version model_objects demo 1 # list model objects

zenml model version deployments demo 1 # list deployments - none

zenml model version runs demo 1 # list runs

python3 predict.py

zenml model version list demo # no new model version created, just consumning existing model

zenml model version artifacts demo 1 # list dataset and predictions artifacts

python3 predict.py

zenml model version artifacts demo 1 # list dataset and predictions (2 versions now) artifacts

zenml model version runs demo 1 # list runs, prediction runs are also here