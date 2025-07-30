import csv
import json
import os
import time


from lib.models.search_target_response import SearchTargetResponse
from lib.complex_encoder import ComplexEncoder
from datetime import datetime

# from lib.file_cache_decorator import file_cached
from lib.utils import shell_exec
from lib.elasticsearch import es_client, set_es_config


def load_config(path: str, **kwargs):
    print(f"Load config from {path}")

    outfile = "/tmp/es-config"
    resp = shell_exec(
        "bash", f'./applications/{kwargs["app"]}/get-config.sh', path, outfile
    )
    print(
        f"  Config resp: \n=====================================\n{resp}\n====================================="
    )

    with open(outfile) as f:
        es_config = json.loads(f.read())
    os.remove(outfile)

    return es_config


class Run:
    def __init__(self, **kwargs):
        self.report = kwargs["report"]
        self.commit_id = kwargs.get("commit_id", None)
        self.previous_commit_id = kwargs.get("previous_commit_id", None)
        self.commit_description = kwargs.get("commit_description", None)
        self.explicit_base_dir = kwargs.get("base_dir", None) is not None
        self.base_dir = kwargs.get("base_dir", f"/tmp/{self.report.app}")
        self.commit_date = kwargs.get("commit_date", None)
        self.run_date = kwargs.get("run_date", None)

        self.created_date = datetime.now()
        self.responses = []

    def change_url(self):
        if self.previous_commit_id is None:
            return None
        return f"https://github.com/NYPL/discovery-api/compare/{self.previous_commit_id}...{self.commit_id}"

    def commit_date_formatted(self):
        return self.commit_date.strftime("%b %d, %Y")

    def app_version(self):
        official_commits = []
        with open(f"./applications/{self.report.app}/commits.csv") as f:
            official_commits = [r["commit"] for r in csv.DictReader(f)]
        if self.commit_id not in official_commits:
            return "CANDIDATE"
        ind = official_commits.index(self.commit_id)
        return f"V{ind + 1}"

    def get_commit_id(self):
        s = shell_exec("git", "-C", self.base_dir, "show", "-s", "--format=%H")
        self.commit_id = s
        return self.commit_id

    def get_commit_date(self):
        cache_path = (
            f"./applications/{self.report.app}/builds/{self.commit_id}.meta.json"
        )
        if os.path.exists(cache_path):
            print("Using cached commit date")
            with open(cache_path, "r") as f:
                meta = json.loads(f.read())
                self.commit_date = datetime.fromisoformat(meta["commit_date"])
        else:
            print(f"Fetching fresh commit date because DNE {cache_path}")
            s = shell_exec(
                "git", "-C", self.base_dir, "show", self.commit_id, "-s", "--format=%ci"
            )
            self.commit_date = datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")

        return self.commit_date

    def get_query(self, params):
        infile = "/tmp/query-infile"
        outfile = "/tmp/query-outfile"

        with open(infile, "w") as f:
            f.write(json.dumps(params))

        path = self.base_dir
        shell_exec(
            "bash",
            f"./applications/{self.report.app}/get-query.sh",
            path,
            infile,
            outfile,
        )

        query = None
        with open(outfile, "r") as f:
            query = json.loads(f.read())

        return query

    def matching_documents(self, query, **kwargs):
        client = es_client()

        count = kwargs.get('count', 25)
        fields = ["title", "creatorLiteral"]
        resp = client.search(index=self.es_config["index"], query=query, source_includes=fields, size=count, track_total_hits=True)
        hits = []
        total = 0
        if resp.get('hits') and resp['hits'].get('hits'):
            total = int(resp['hits']['total']['value'])
            for hit in resp['hits']['hits']:
                for field in fields:
                    if hit['_source'].get(field) and type(hit['_source'][field]) is list and len(hit['_source'][field]) > 0:
                        hit['_source'][field] = hit['_source'][field][0]
                hits.append(hit)
        return hits, total

    def rank_eval_call(self, target, query):
        ratings = [
            {
                "_index": self.es_config["index"],
                "_id": relevantId,
                # Higher "rating" indicates higher importance, but 'precision at
                # k' doesn't care about order, so set them all to 1, the default
                # relevant_rating_threshold:
                "rating": 1,
            }
            for relevantId in target.relevant
        ]

        request = {
            "id": "report",
            "request": {"query": query, "_source": {"includes": ["uri"]}},
            "ratings": ratings,
        }

        metric = {
            f"{target.metric}": {
                "k": target.metric_at,
                "relevant_rating_threshold": 1,
            }
        }
        call = {"requests": [request], "metric": metric}

        return call

    def initialize_es_client(self):
        # TODO: Hack to override the es config for the first commit to use
        #  - the host and creds of the second registered commit and
        #  - a custom index (a v8 snapshot of the old ES5.3 index)
        if self.commit_id == "379a05103adb2e79fb5469a2b2ef3adba5385744":
            print("  Overriding es-config for first commit")

            # Load ES config from 2nd commit, since it uses our v8 cluster:
            self.initialize_app(commit_id="ef2d69fcf119d3ec8f5261d77fb2732d9f7ce44f")
            self.es_config = load_config(self.base_dir, app=self.report.app)

            # Override the 2nd commit's configured index to use legacy snapshot:
            self.es_config["index"] = "resources-2018-04-09"

            # Now, reinitialize:
            self.initialize_app()
        else:
            self.es_config = load_config(self.base_dir, app=self.report.app)

        set_es_config(self.es_config)

    def initialize_app(self, use_cache=True, commit_id=None):
        if commit_id is None:
            commit_id = self.commit_id

        package_path = f"./applications/{self.report.app}/builds/{commit_id}.zip"
        if use_cache and os.path.isfile(package_path):
            print(f"Using built package: {package_path}")

            cmd = ["bash", "./unpackage.sh", package_path, self.base_dir]
            print(f"CMD: {' '.join(cmd)}")
            resp = shell_exec(*cmd)
            print(
                f"  Unpackage resp: \n=====================================\n{resp}\n====================================="
            )

        else:
            print(f"  Initializing commit {commit_id} in {self.base_dir}")
            resp = shell_exec(
                "bash",
                f"./applications/{self.report.app}/initialize.sh",
                self.base_dir,
                commit_id,
            )
            print(
                f"  Initialize resp: \n=====================================\n{resp}\n====================================="
            )

    def package_app(self):
        cmd = ["bash", "./package.sh", self.base_dir, self.report.app, self.commit_id]
        print(f"CMD: {' '.join(cmd)}")
        resp = shell_exec(*cmd)
        print(
            f"  Package app resp: \n=====================================\n{resp}\n====================================="
        )

        cache_path = (
            f"./applications/{self.report.app}/builds/{self.commit_id}.meta.json"
        )
        commit_date = self.get_commit_date().isoformat()
        with open(cache_path, "w") as f:
            meta = {"commit_date": commit_date}
            print(f"writing {json.dumps(meta)} to {cache_path}")
            f.write(json.dumps(meta))

    def collect_data(self, previous_run):
        print(f"Collecting run data for {self.commit_id}")

        current_targets = [t for t in self.report.targets]
        current_target_keys = [t.key for t in current_targets]

        deprecated_target_keys = []
        previous_target_keys = []
        if previous_run is not None:
            previous_target_keys = [
                response.target.key for response in previous_run.responses
            ]
            deprecated_target_keys = [
                key for key in previous_target_keys if key not in current_target_keys
            ]

        if len(deprecated_target_keys) > 0:
            print(f"  Deprecating targets: {deprecated_target_keys}")

        new_targets = [t for t in current_targets if t.key not in previous_target_keys]
        if len(new_targets) == 0:
            self.responses = [
                r.raw
                for r in previous_run.responses
                if r.target.key not in deprecated_target_keys
            ]
            self.run_date = previous_run.run_date
            self.commit_id = previous_run.commit_id
            self.commit_date = previous_run.commit_date

            print(f"  Skipping re-running {self.commit_id} because nothing changed")
            return

        if (
            not self.explicit_base_dir
            and self.commit_id != "379a05103adb2e79fb5469a2b2ef3adba5385744"
        ):
            self.initialize_app()

        self.initialize_es_client()

        self.run_date = datetime.now().isoformat()

        self.run_targets(previous_run)

        if self.commit_id is None:
            self.get_commit_id()
        self.get_commit_date()

    def run_targets(self, previous_run):
        print(f"Running {len(self.report.targets)} targets for {self.commit_id}")

        for ind, target in enumerate(self.report.targets):
            print(f"  Running target {ind}: {target.key}")
            previous_response = None
            if previous_run is not None:
                _previous_response = [
                    r for r in previous_run.responses if r.target.key == target.key
                ]
                previous_response = (
                    _previous_response[0] if len(_previous_response) > 0 else None
                )
            if previous_response is not None:
                print(
                    f"    Skipping re-running {self.commit_id}: {target.key} because nothing changed"
                )
                self.responses.append(previous_response.raw)
                continue

            params = {"search_scope": target.search_scope, "q": target.q}
            query = self.get_query(params)
            call = self.rank_eval_call(target, query)

            print(f"    Running rank_eval call for {params}")
            response = None
            response = self.es_rank_eval(
                requests=call["requests"],
                metric=call["metric"],
                index=self.es_config["index"]
            )

            start_time = time.time()
            matching_documents, count = self.matching_documents(query, count=max(target.metric_at + 10, 25))
            elapsed = round((time.time() - start_time) * 1000)

            for ind, doc in enumerate(matching_documents):
                if doc['_id'] in target.relevant:
                    doc['relevant'] = True
                if ind < target.metric_at:
                    doc['within_metric'] = True

            if response["failures"].get("report") is not None:
                print(f'Got Error: {response["failures"]}')
                exit()

            self.responses.append(
                {
                    "target": target,
                    "response": response.body,
                    "matching_documents": matching_documents,
                    "query": query,
                    "elapsed": elapsed,
                    "count": count,
                }
            )

    def es_count(self, query):
        client = es_client()
        resp = client.count(query=query)
        return resp["count"]

    # @file_cached
    def es_rank_eval(self, **kwargs):
        client = es_client()
        return client.rank_eval(**kwargs)

    def jsonable(self):
        copy = dict(self.__dict__)
        if "es_config" in copy:
            del copy["es_config"]
        return copy

    def save_manifest(self, basedir):
        serialization = json.dumps(
            self.jsonable(), indent=2, sort_keys=True, cls=ComplexEncoder
        )

        print(f"  Saving manifest for {self.commit_id}")

        os.makedirs(basedir, exist_ok=True)

        path = self.manifest_file_path(basedir)
        with open(path, "w") as f:
            f.write(serialization)
        print(f"  Wrote to {path}")

    def manifest_file_path(self, basedir):
        file_key = "current" if self.explicit_base_dir else self.commit_id
        filename = f"{file_key}.json"
        return os.path.join(basedir, filename)

    @staticmethod
    def for_commit(report, commit, description=""):
        print(f"Building Run for {commit}")
        return Run(report=report, commit_id=commit, commit_description=description)

    @staticmethod
    def for_path(report, path, description=""):
        print(f"Building Run for {path}")
        return Run(report=report, commit_description=description, base_dir=path)

    @staticmethod
    def from_json(report, json, **kwargs):
        run = Run(
            report=report,
            commit_id=json["commit_id"],
            commit_description=json["commit_description"],
            commit_date=datetime.fromisoformat(json["commit_date"]),
            previous_commit_id=kwargs.get("previous_commit_id"),
            run_date=json["run_date"],
        )

        run.responses = [
            SearchTargetResponse.from_json(r, run=run) for r in json["responses"]
        ]

        return run
