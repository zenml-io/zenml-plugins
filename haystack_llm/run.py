import os
from typing import Type

from zenml.enums import ArtifactType
from zenml.io import fileio
from zenml.materializers.base_materializer import BaseMaterializer
from haystack.document_stores import InMemoryDocumentStore
from haystack.utils import build_pipeline, add_example_data, print_answers
from zenml import pipeline, step
from haystack.pipelines import Pipeline as HaystackPipeline

# We are model agnostic :) Here, you can choose from: "anthropic", "cohere", "huggingface", and "openai".
provider = "openai"
API_KEY = "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"  # ADD YOUR KEY HERE


class HaystackPipelineMaterializer(BaseMaterializer):
    ASSOCIATED_TYPES = (HaystackPipeline,)
    ASSOCIATED_ARTIFACT_TYPE = ArtifactType.DATA

    def load(self, data_type: Type[HaystackPipeline]) -> HaystackPipeline:
        """Read from artifact store."""
        return HaystackPipeline.load_from_yaml(os.path.join(self.uri, "pipeline.yaml"))

    def save(self, my_obj: HaystackPipeline) -> None:
        """Write to artifact store."""
        my_obj.save_to_yaml(os.path.join(self.uri, "pipeline.yaml"))



@step(output_materializers=HaystackPipelineMaterializer)
def get_pipeline() -> HaystackPipeline:
    # Download and add Game of Thrones TXT articles to Haystack DocumentStore.
    # You can also provide a folder with your local documents.
    document_store = InMemoryDocumentStore(use_bm25=True)
    add_example_data(document_store, "data/GoT_getting_started")

    return build_pipeline(provider, API_KEY, document_store)


@step
def run_query(pipeline: HaystackPipeline):
    # Ask a question on the data you just added.
    result = pipeline.run(query="Who is the father of Arya Stark?")

    # For details, like which documents were used to generate the answer, look into the <result> object
    print_answers(result, details="medium")


@pipeline
def haystack_pipeline():
    pipeline = get_pipeline()
    run_query(pipeline)


if __name__ == "__main__":
    haystack_pipeline()
