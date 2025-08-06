import json

from lib.models.search_target import SearchTarget
from lib.report_utils import basic_bib_metadata
from lib.utils import format_float


class SearchTargetResponse:
    def __init__(self, **kwargs):
        self.target = kwargs["target"]
        self.elapsed = kwargs["elapsed"]
        self.matching_documents = kwargs.get("matching_documents")
        self.count = kwargs["count"]
        self.raw = kwargs.get("raw")

        report = None
        if kwargs.get("response"):
            self.metric_score = kwargs["response"]["metric_score"]
            if kwargs["response"].get("details"):
                report = kwargs["response"]["details"]["report"]

                self.hits = [
                    {
                        "bnum": hit["hit"]["_id"],
                        "found": hit.get("rating") is not None
                    }
                    for hit in report["hits"]
                    # if hit.get("rating", None) is not None
                ]
                self.hits = [{**hit, **basic_bib_metadata(hit["bnum"])} for hit in self.hits]
                self.found = len([h for h in self.hits if h["found"]])

        self.hits_length = 0
        if report.get("metric_details") is not None:
            self.hits_length = list(report["metric_details"].values())[0].get(
                "relevant_docs_retrieved"
            )

        self.run = kwargs.get("run")

    def metric_score_formatted(self):
        return format_float(self.metric_score)

    def elapsed_formatted(self):
        return format_float(self.ellpased)

    @staticmethod
    def from_json(obj, **kwargs):
        # print(f"RunResponse.from_json {obj}")
        props = {**obj}
        props["target"] = SearchTarget.from_json(obj["target"])
        # print(f"SearchTargetResponse from: {json.dumps(obj, indent=2)}")
        props["run"] = kwargs["run"]
        props["raw"] = obj
        search_target_response = SearchTargetResponse(**props)
        return search_target_response
