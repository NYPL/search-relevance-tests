from elasticsearch import Elasticsearch


es_config = None


def set_es_config(config):
    global es_config

    es_config = config


_es_client = None


def es_client():
    global _es_client

    if es_config is None:
        raise "Error: no es_config"

    if _es_client is None:
        nodes = es_config["nodes"].split(",")

        api_key = es_config.get("apiKey")

        _es_client = Elasticsearch(nodes, api_key=api_key)

    return _es_client
