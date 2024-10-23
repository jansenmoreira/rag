import argparse
import logging
import time
from urllib.parse import urljoin

import requests
import urllib3
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

urllib3.disable_warnings()


class OpenSearchManager:
    def __init__(self, base_url, user, password, ssl=False):
        self.base_url = base_url
        self.params = {
            "headers": {"Content-Type": "application/json"},
            "auth": HTTPBasicAuth(user, password),
            "verify": ssl,
        }

    def delete_resource(self, target):
        endpoint = urljoin(self.base_url, target)
        response = requests.delete(endpoint, **self.params)

        if not (response.status_code == 200 or response.status_code == 404):
            raise RuntimeError(response.text)

    def await_task(self, task_id, success="COMPLETED", failure="FAILED"):
        logger.info(f"Waiting task {task_id} state to be {success}")

        while True:
            endpoint = urljoin(self.base_url, f"_plugins/_ml/tasks/{task_id}")
            response = requests.get(endpoint, **self.params)

            if response.status_code != 200:
                raise RuntimeError(response.text)

            state = response.json()["state"]

            if state == success:
                logger.info(f"Task {task_id} succeeded!")
                return response.json()
            elif state == failure:
                raise RuntimeError(f"Task {task_id} failed!")

            logger.info(f"Task {task_id} state is {state}, waiting 1 second...")
            time.sleep(1)

    def setup_cluster(self):
        logger.info("Setting cluster configuration")

        endpoint = urljoin(self.base_url, "_cluster/settings")
        payload = {
            "persistent": {
                "plugins.ml_commons.only_run_on_ml_node": False,
                "plugins.ml_commons.model_access_control_enabled": True,
                "plugins.ml_commons.model_auto_redeploy.enable": True,
            }
        }

        response = requests.put(endpoint, json=payload, **self.params)

        if response.status_code != 200:
            raise RuntimeError(response.text)

    def delete_models(self, model, version):
        logger.info("Deleting existing models")

        search_endpoint = urljoin(self.base_url, "_plugins/_ml/models/_search")

        payload = {"query": {"match_all": {}}}

        search_response = requests.post(search_endpoint, json=payload, **self.params)

        if search_response.status_code != 200:
            raise RuntimeError(search_response.text)

        models_ids = {
            m["_source"].get("model_id") for m in search_response.json()["hits"]["hits"]
        }
        models_ids = {m for m in models_ids if m is not None}

        if len(models_ids) > 0:
            logger.info(f"Models found: {','.join(models_ids)}")

        for model_id in models_ids:
            logger.info(f"Undeploying model {model_id}")

            undeploy_endpoint = urljoin(
                self.base_url, f"/_plugins/_ml/models/{model_id}/_undeploy"
            )
            undeploy_response = requests.post(undeploy_endpoint, **self.params)

            if not (
                undeploy_response.status_code == 200
                or undeploy_response.status_code == 404
            ):
                raise RuntimeError(undeploy_response.text)

            logger.info(f"Deleting model {model_id}")

            self.delete_resource(f"/_plugins/_ml/models/{model_id}")

    def deploy_model(self, model, version):
        self.delete_models(model, version)

        logger.info(f"Deploying model '{model}' version '{version}'")

        endpoint = urljoin(self.base_url, "_plugins/_ml/models/_register?deploy=true")

        payload = {"name": model, "version": version, "model_format": "TORCH_SCRIPT"}

        response = requests.post(
            endpoint,
            json=payload,
            **self.params,
        )

        if response.status_code != 200:
            raise RuntimeError(response.text)

        task_id = response.json()["task_id"]
        result = self.await_task(task_id)

        model_id = result["model_id"]

        logger.info(f"Model id is {model_id}")

        return model_id

    def create_search_pipeline(self, pipeline_id, model_id):
        logger.info(
            f"Recreating search pipeline '{pipeline_id}' using model '{model_id}'"
        )

        self.delete_resource(f"/_search/pipeline/{pipeline_id}")

        endpoint = urljoin(self.base_url, f"/_search/pipeline/{pipeline_id}")

        payload = {
            "request_processors": [
                {"neural_query_enricher": {"default_model_id": model_id}}
            ]
        }

        response = requests.put(
            endpoint,
            json=payload,
            **self.params,
        )

        if response.status_code != 200:
            raise RuntimeError(response.text)

    def create_ingest_pipeline(self, pipeline_id, model_id, source, target):
        logger.info(
            f"Recreating ingest pipeline '{pipeline_id}' using model '{model_id}'"
        )

        self.delete_resource(f"/_ingest/pipeline/{pipeline_id}")

        endpoint = urljoin(self.base_url, f"/_ingest/pipeline/{pipeline_id}")

        payload = {
            "description": f"Ingestion pipeline that maps '{source}' to '{target}' using '{model_id}'",
            "processors": [
                {
                    "text_embedding": {
                        "model_id": model_id,
                        "field_map": {source: target},
                    }
                }
            ],
        }

        response = requests.put(
            endpoint,
            json=payload,
            **self.params,
        )

        if response.status_code != 200:
            raise RuntimeError(response.text)

    def create_index(self, name, model_id, field, vector_size):
        pipeline_id = f"{name}_pipeline"
        source_field = field
        target_field = f"{field}_embedding"

        logger.info(f"Deleting index '{name}'")

        self.delete_resource(name)

        self.create_search_pipeline(pipeline_id, model_id)
        self.create_ingest_pipeline(pipeline_id, model_id, source_field, target_field)

        logger.info(f"Creating index '{name}'")

        endpoint = urljoin(self.base_url, name)

        payload = {
            "mappings": {
                "properties": {
                    source_field: {"type": "text"},
                    target_field: {
                        "type": "knn_vector",
                        "dimension": vector_size,
                        "method": {
                            "name": "hnsw",
                            "engine": "lucene",
                            "parameters": {"ef_construction": 128, "m": 32},
                        },
                    },
                }
            },
            "settings": {
                "index": {
                    "knn.space_type": "cosinesimil",
                    "default_pipeline": pipeline_id,
                    "knn": True,
                    "knn.algo_param.ef_search": 128,
                    "search": {"default_pipeline": pipeline_id},
                },
            },
        }

        response = requests.put(
            endpoint,
            json=payload,
            **self.params,
        )

        if response.status_code != 200:
            raise RuntimeError(response.text)


def main():
    parser = argparse.ArgumentParser(
        prog="opensearch-manager",
        description="OpenSearch setup script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-m",
        "--model",
        default="huggingface/sentence-transformers/all-mpnet-base-v2",
        help="Model name to be deployed on OpenSearch",
    )

    parser.add_argument(
        "-v",
        "--version",
        default="1.0.1",
        help="Model version to be deployed on OpenSearch",
    )

    parser.add_argument(
        "-U", "--url", default="https://127.0.0.1:9200", help="OpenSearch base URL"
    )

    parser.add_argument("-u", "--user", default="admin", help="OpenSearch username")

    parser.add_argument(
        "-p", "--password", default="#Admin1234", help="OpenSearch password"
    )

    parser.add_argument(
        "-n", "--index-name", default="sentences", help="OpenSearch kNN index name"
    )

    parser.add_argument(
        "-s", "--vector-size", default=768, help="OpenSearch kNN vector size"
    )

    args = parser.parse_args()

    manager = OpenSearchManager(args.url, args.user, args.password)

    manager.setup_cluster()
    model_id = manager.deploy_model(args.model, args.version)
    manager.create_index(args.index_name, model_id, "sentence", args.vector_size)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
    )
    main()
