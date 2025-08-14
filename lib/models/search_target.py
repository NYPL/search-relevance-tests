import yaml

from lib.report_utils import basic_bib_metadata


class SearchTarget:
    def __init__(self, **kwargs):
        self.q = kwargs["q"]
        self.search_scope = kwargs["search_scope"]
        self.metric = kwargs["metric"]
        self.metric_at = kwargs["metric_at"]
        self.relevant = kwargs["relevant"]
        self.notes = kwargs.get("notes")
        self.key = (
            "|".join(
                [
                    self.q,
                    self.search_scope,
                    self.metric,
                    str(self.metric_at),
                    *self.relevant,
                ]
            )
            .replace("'", "-apos-")
            .replace('"', "-quot-")
            .replace("?", "-quest-")
            .replace(" ", "_")
        )

        self.qa_url = f"https://qa-www.nypl.org/research/research-catalog/search?q={self.q}&search_scope={self.search_scope}"
        self.production_url = f"https://www.nypl.org/research/research-catalog/search?q={self.q}&search_scope={self.search_scope}"

    def relevant_records(self):
        return [basic_bib_metadata(bnum) for bnum in self.relevant]

    def relevant_length(self):
        return len(self.relevant)

    def jsonable(self):
        return self.__dict__

    def __eq__(self, other):
        return self.q == other.q

    def __str__(self):
        return f"<SearchTarget {self.key}>"

    @staticmethod
    def from_json(json):
        return SearchTarget(
            q=json["q"],
            search_scope=json["search_scope"],
            metric=json["metric"],
            metric_at=json["metric_at"],
            relevant=json["relevant"],
            notes=json.get("notes", None),
        )

    @staticmethod
    def load_all_from(path):
        with open(path) as f:
            return [
                SearchTarget.from_json(t)
                for t in yaml.safe_load_all(f)
                if t is not None
            ]
