import json
import os
import time

from lib.models.app_config import AppConfig
from lib.models.search_target_response import SearchTargetResponse
from lib.complex_encoder import ComplexEncoder
from datetime import datetime
from lib.filestore import download_dir
from lib.utils import shell_exec
from lib.elasticsearch import es_client, set_es_config
from nypl_py_utils.functions.log_helper import create_log


class Run:
    def __init__(self, **kwargs):
        self.app_config = kwargs["app_config"]
        self.base_dir = kwargs.get("base_dir", self.app_config.local_temp_path("app"))
        self.commit_id = kwargs.get("commit_id", self.get_commit_id())
        self.previous_commit_id = kwargs.get("previous_commit_id", None)
        self.commit_description = kwargs.get("commit_description", None)
        self.explicit_base_dir = kwargs.get("base_dir", None) is not None
        self.file_key = kwargs.get("file_key", self.commit_id)
        self.commit_date = kwargs.get("commit_date", None)
        self.run_date = kwargs.get("run_date", None)

        self.created_date = datetime.now()
        self.responses = []

        self.logger = create_log(__name__)

    def change_url(self):
        if self.previous_commit_id is None:
            return None
        return f"https://github.com/NYPL/discovery-api/compare/{self.previous_commit_id}...{self.commit_id}"

    def commit_date_formatted(self):
        return self.commit_date.strftime("%b %d, %Y")

    def is_local(self):
        return self.file_key == "local"

    def is_latest(self):
        return self.file_key == "latest"

    def app_version(self):
        if self.file_key in ["latest", "local"]:
            return self.file_key.upper()
        official_commit_ids = [c["commit"] for c in self.app_config.official_commits()]
        if self.commit_id not in official_commit_ids:
            return None
        ind = official_commit_ids.index(self.commit_id)
        return f"V{ind + 1}"

    def get_commit_id(self):
        s = shell_exec("git", "-C", self.base_dir, "show", "-s", "--format=%H")
        self.commit_id = s
        return self.commit_id

    def get_commit_date(self):
        cache_path = f"./applications/{self.app_config.app_name}/builds/{self.commit_id}.meta.json"
        if os.path.exists(cache_path):
            self.logger.debug("Using cached commit date")
            with open(cache_path, "r") as f:
                meta = json.loads(f.read())
                self.commit_date = datetime.fromisoformat(meta["commit_date"])
        else:
            self.logger.debug(f"Fetching fresh commit date because DNE {cache_path}")
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
            f"./applications/{self.app_config.app_name}/get-query.sh",
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

        count = kwargs.get("count", 25)
        fields = ["title", "creatorLiteral"]
        highlight = {"order": "score", "fields": {"*": {}}}
        resp = client.search(
            index=self.es_config["index"],
            query=query,
            source_includes=fields,
            size=count,
            track_total_hits=True,
            highlight=highlight,
        )
        hits = []
        total = 0
        if resp.get("hits") and resp["hits"].get("hits"):
            total = int(resp["hits"]["total"]["value"])
            for hit in resp["hits"]["hits"]:
                for field in fields:
                    if (
                        hit["_source"].get(field)
                        and type(hit["_source"][field]) is list
                        and len(hit["_source"][field]) > 0
                    ):
                        hit["_source"][field] = hit["_source"][field][0]
                if "highlight" in hit:
                    hit["highlight"] = [
                        {"field": field, "values": values}
                        for field, values in hit["highlight"].items()
                        if field
                        not in ["nyplSource", "buildingLocationIds", "issuance.id"]
                    ]
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
            self.logger.info("  Overriding es-config for first commit")

            # Load ES config from 2nd commit, since it uses our v8 cluster:
            self.initialize_app(commit_id="ef2d69fcf119d3ec8f5261d77fb2732d9f7ce44f")
            self.es_config = self.app_config.load_es_config(self.base_dir)

            # Override the 2nd commit's configured index to use legacy snapshot:
            self.es_config["index"] = "resources-2018-04-09"

            # Now, reinitialize:
            self.initialize_app()
        else:
            self.es_config = self.app_config.load_es_config(self.base_dir)

        set_es_config(self.es_config)

    def initialize_app(self, use_cache=True, commit_id=None):
        if commit_id is None:
            commit_id = self.commit_id

        package_path = os.path.join(
            self.app_config.local_config_path(), "builds", f"{commit_id}.zip"
        )
        if use_cache and os.path.isfile(package_path):
            print("--------------------------------------------------")
            print(f"| Using built package: {package_path}")
            print("--------------------------------------------------")

            cmd = ["bash", "./unpackage.sh", package_path, self.base_dir]
            self.logger.debug(f"CMD: {' '.join(cmd)}")
            shell_exec(*cmd)
            print("--------------------------------------------------")
            """
            print(
                f"  Unpackage resp: \n=====================================\n{resp}\n====================================="
            )
            """

        else:
            print("--------------------------------------------------")
            print(f"| Initializing commit {commit_id} in {self.base_dir}")
            print("--------------------------------------------------")
            shell_exec(
                "bash",
                os.path.join(self.app_config.local_config_path(), "initialize.sh"),
                self.base_dir,
                commit_id,
            )
            print("--------------------------------------------------")
            """
            print(
                f"  Initialize resp: \n=====================================\n{resp}\n====================================="
            )
            """

    def package_app(self):
        cmd = [
            "bash",
            "./package.sh",
            self.base_dir,
            self.app_config.app_name,
            self.commit_id,
        ]
        self.logger.debug(f"CMD: {' '.join(cmd)}")
        shell_exec(*cmd)
        """
        print(
            f"  Package app resp: \n=====================================\n{resp}\n====================================="
        )
        """

        cache_path = os.path.join(
            self.app_config.local_config_path(), "builds", f"{self.commit_id}.meta.json"
        )
        commit_date = self.get_commit_date().isoformat()
        with open(cache_path, "w") as f:
            meta = {"commit_date": commit_date}
            self.logger.debug(f"writing {json.dumps(meta)} to {cache_path}")
            f.write(json.dumps(meta))

    def collect_data(self, rebuild=False):
        self.logger.info(f"Collecting run data for {self.commit_id}")
        previous_run = Run.by_manifest_file(self.app_config, self.commit_id)

        if rebuild:
            previous_run = None

        current_targets = [t for t in self.app_config.targets]
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
            self.logger.debug(f"  Deprecating targets: {deprecated_target_keys}")

        new_targets = [t for t in current_targets if t.key not in previous_target_keys]
        if len(new_targets) == 0:
            self.responses = [
                SearchTargetResponse.from_json(r.raw, run=self)
                for r in previous_run.responses
                if r.target.key not in deprecated_target_keys
            ]
            self.run_date = previous_run.run_date
            self.commit_id = previous_run.commit_id
            self.commit_date = previous_run.commit_date

            self.logger.info(
                f"  Skipping re-running {self.commit_id} because nothing changed"
            )
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

        if not self.explicit_base_dir:
            self.get_commit_date()

    def run_targets(self, previous_run):
        for_what = self.base_dir if self.commit_id is None else self.commit_id
        self.logger.info(
            f"Running {len(self.app_config.targets)} targets for {for_what}"
        )

        for ind, target in enumerate(self.app_config.targets):
            self.logger.info(f"  Running target {ind}: {target.key}")
            previous_response = None
            if previous_run is not None:
                _previous_response = [
                    r for r in previous_run.responses if r.target.key == target.key
                ]
                previous_response = (
                    _previous_response[0] if len(_previous_response) > 0 else None
                )
            if previous_response is not None:
                self.logger.info(
                    f"    Skipping re-running {self.commit_id}: {target.key} because nothing changed"
                )
                self.responses.append(
                    SearchTargetResponse.from_json(previous_response.raw, self)
                )
                continue

            params = {"search_scope": target.search_scope, "q": target.q}
            query = self.get_query(params)
            call = self.rank_eval_call(target, query)

            self.logger.debug(f"    Running rank_eval call for {params}")
            response = None
            response = self.es_rank_eval(
                requests=call["requests"],
                metric=call["metric"],
                index=self.es_config["index"],
            )

            start_time = time.time()
            matching_documents, count = self.matching_documents(
                query, count=max(target.metric_at + 10, 25)
            )
            elapsed = round((time.time() - start_time) * 1000)

            for ind, doc in enumerate(matching_documents):
                if doc["_id"] in target.relevant:
                    doc["relevant"] = True
                if ind < target.metric_at:
                    doc["within_metric"] = True

            if response["failures"].get("report") is not None:
                self.logger.error(f'Got Error: {response["failures"]}')
                exit()

            self.responses.append(
                SearchTargetResponse.from_json(
                    {
                        "target": target,
                        "response": response,
                        "matching_documents": matching_documents,
                        "query": query,
                        "elapsed": elapsed,
                        "count": count,
                    }
                )
            )

    def es_count(self, query):
        client = es_client()
        resp = client.count(query=query)
        return resp["count"]

    def es_rank_eval(self, **kwargs):
        client = es_client()
        return client.rank_eval(**kwargs)

    def jsonable(self):
        copy = dict(self.__dict__)
        for p in ["es_config", "logger"]:
            if p in copy:
                del copy[p]
        return copy

    def save_manifest(self):
        serialization = json.dumps(
            self.jsonable(), indent=2, sort_keys=True, cls=ComplexEncoder
        )
        self.logger.debug(f"  Saving manifest for {self.commit_id}")

        basedir = self.app_config.local_temp_path("manifests")
        os.makedirs(basedir, exist_ok=True)

        path = self.manifest_file_path(basedir)
        with open(path, "w") as f:
            f.write(serialization)
        self.logger.debug(f"  Wrote to {path}")

    def manifest_file_path(self, basedir):
        filename = f"{self.file_key}.json"
        return os.path.join(basedir, filename)

    def has_equivalent_scores(self, other):
        scores1 = [resp.metric_score for resp in self.responses]
        scores2 = [resp.metric_score for resp in other.responses]

        if len(scores1) != len(scores2):
            return False, f"Mismatched scores lengths: {len(scores1)} != {len(scores2)}"
        diffs = [
            (ind, scores1[ind], scores2[ind])
            for ind in range(len(scores1))
            if scores1[ind] != scores2[ind]
        ]
        if len(diffs):
            summaries = [f"T{ind+1}: {s1} => {s2}" for ind, s1, s2 in diffs]
            return False, f"Mismatched scores: {', '.join(summaries)}"

        return True, None

    @staticmethod
    def for_commit(app_config, commit, description=""):
        create_log(__name__).info(f"Building Run for {commit}")
        return Run(
            app_config=app_config, commit_id=commit, commit_description=description
        )

    @staticmethod
    def for_path(app_config, path, description="", file_key=None):
        create_log(__name__).info(f"Building Run for {path}")
        return Run(
            app_config=app_config,
            commit_description=description,
            commit_date=datetime.now(),
            base_dir=path,
            file_key=file_key,
        )

    @staticmethod
    def from_json(app_config: AppConfig, json, **kwargs):
        run = Run(
            app_config=app_config,
            commit_id=json["commit_id"],
            commit_description=json["commit_description"],
            commit_date=datetime.fromisoformat(json["commit_date"]),
            previous_commit_id=kwargs.get("previous_commit_id"),
            run_date=json["run_date"],
            file_key=json.get("file_key"),
        )

        run.responses = [
            SearchTargetResponse.from_json(r, run=run) for r in json["responses"]
        ]

        return run

    @staticmethod
    def by_manifest_file(app_config, commit_id):
        path = os.path.join(
            app_config.local_temp_path("manifests"), f"{commit_id}.json"
        )
        if os.path.exists(path):
            with open(path) as f:
                return Run.from_json(app_config, json.loads(f.read()))
        return None

    @staticmethod
    def all_from_manifests(app_config, include_local=False, include_latest=False):
        directory = app_config.local_temp_path("manifests")
        download_dir(f"srt/{app_config.app_name}/manifests", directory)

        commits = app_config.official_commits()

        manifest_paths = []
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            is_official_commit = filename not in [
                f'{c["commit"]}.json' for c in commits
            ]
            is_permitted_local = filename == "local.json" and include_local
            is_permitted_latest = filename == "latest.json" and include_latest
            if (
                is_official_commit
                and not is_permitted_local
                and not is_permitted_latest
            ):
                create_log(__name__).info(
                    f"Not including manifest {filename} because not in official commits."
                )

            elif filename.endswith(".json"):
                manifest_paths.append(os.path.join(str(directory), filename))

        manifests = []
        for path in manifest_paths:
            with open(path) as f:
                manifests.append(json.loads(f.read()))

        manifests.sort(key=lambda manifest: manifest["commit_date"])

        runs = []
        for ind, manifest in enumerate(manifests):
            previous_commit_id = manifests[ind - 1]["commit_id"] if ind > 0 else None
            run = Run.from_json(
                app_config, manifest, previous_commit_id=previous_commit_id
            )
            runs.append(run)

        for ind, run in enumerate(runs):
            create_log(__name__).info(
                f"Loaded run: {manifest_paths[ind]} - {run.commit_date} - {len(run.responses)} responses"
            )
        return runs
