import csv
from datetime import datetime
import json
import os
import pystache

from lib.models.run import Run
from lib.models.search_target import SearchTarget
from lib.graphs import create_graph
from lib.utils import format_float, average_by_index, local_application_file
from lib.report_utils import normalize_run_data, normalize_overall_run_data
from lib.filestore import upload_dir, download_dir


class Report:
    def __init__(self, app: str):
        self.app = app

        self.targets = []
        self.runs = []

    def jsonable(self):
        return {"app": self.app}

    def load_targets(self, **kwargs):
        path = local_application_file(self.app, "targets.yaml")

        self.targets = SearchTarget.load_all_from(path)

        if kwargs.get("rows", None) is not None:
            self.targets = [self.targets[r] for r in kwargs["rows"]]

    def add_run(self, base_dir, description):
        self.runs.append(Run.for_path(self, base_dir, description))

    def previous_run_for(self, run, previous_runs):
        for previous_run in previous_runs:
            if run.commit_id == previous_run.commit_id:
                return previous_run

    def collect_data(self, **kwargs):
        previous_runs = self.load_runs_from_manifests()

        for run in self.runs:
            previous_run = None if kwargs.get('rebuild') else self.previous_run_for(run, previous_runs)
            run.collect_data(previous_run)

    def save_manifests(self):
        print("Saving and uploading manifests")
        basedir = f"/tmp/srt/{self.app}/manifests"
        [run.save_manifest(basedir) for run in self.runs]

        upload_dir(basedir, f"srt/{self.app}/manifests")

    def add_registered_runs(self):
        # path = local_application_file(self.app, 'commits.csv')
        path = f"./applications/{self.app}/commits.csv"

        official_commit_runs = []
        with open(path) as f:
            official_commit_runs = [
                Run.for_commit(self, r["commit"], r["description"])
                for r in csv.DictReader(f)
            ]
        self.runs.extend(official_commit_runs)

    def load_from_manifests(self):
        self.runs = self.load_runs_from_manifests()

    def load_runs_from_manifests(self):
        directory = f"/tmp/srt/{self.app}/manifests"
        download_dir(f"srt/{self.app}/manifests", directory)

        manifest_paths = []
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            if filename.endswith(".json"):
                manifest_paths.append(os.path.join(str(directory), filename))

        manifests = []
        for path in manifest_paths:
            with open(path) as f:
                manifests.append(json.loads(f.read()))

        manifests.sort(key=lambda manifest: manifest["commit_date"])

        runs = []
        for ind, manifest in enumerate(manifests):
            previous_commit_id = manifests[ind - 1]["commit_id"] if ind > 0 else None
            run = Run.from_json(self, manifest, previous_commit_id=previous_commit_id)
            runs.append(run)

        for run in runs:
            print(
                f"Loaded run: {run.commit_id} - {run.commit_date} - {len(run.responses)} responses"
            )
        return runs

    def build(self, **kwargs):
        palette = {"red": "#920711", "blue": "#00838a", "orange": "#EC7B1F"}

        basedir = f"/tmp/srt/{self.app}/report"

        os.makedirs(f"{basedir}/graphs", exist_ok=True)

        self.load_targets()

        targets_with_runs = [
            {
                "target": target,
                "number": i + 1,
                "results": self.results_by_target(target),
            }
            for i, target in enumerate(self.targets)
        ]
        targets_with_runs = [r for r in targets_with_runs if len(r["results"]) > 0]

        runs = [result.run for result in targets_with_runs[0]["results"]]
        app_versions = [run.app_version() for run in runs]

        for target_runs in targets_with_runs:
            results = target_runs["results"]
            target = target_runs["target"]
            if len(results) == 0:
                continue

            scores, elapsed, elapsed_relative, counts = normalize_run_data(results)

            create_graph(
                app_versions,
                scores,
                elapsed_relative,
                target.key,
                counts=counts,
                basedir=basedir,
                palette=palette,
                rebuild=kwargs.get("rebuild_graphs", False),
            )

        overall_scores, overall_elapsed, overall_elapsed_relative = (
            normalize_overall_run_data(t["results"] for t in targets_with_runs)
        )

        create_graph(
            app_versions,
            overall_scores,
            overall_elapsed_relative,
            "overall",
            basedir=basedir,
            palette=palette,
            rebuild=kwargs.get("rebuild_graphs", False),
        )

        run_summary = [
            {
                "run": run,
                "average_score": format_float(overall_scores[ind]),
                "average_elapsed": int(overall_elapsed[ind]),
            }
            for ind, run in enumerate(runs)
        ]
        renderer = pystache.Renderer(search_dirs="./templates")

        template_vars = {
            "report_id": datetime.now(),
            "build_time": datetime.now().strftime("%c"),
            "colors": palette,
            "run_summary": as_json(run_summary),
            "targets": as_json(targets_with_runs),
        }
        html = renderer.render("{{>report}}", template_vars)

        with open(f"{basedir}/index.html", "w") as f:
            f.write(html)

        if kwargs.get("persist_to_s3", True):
            upload_dir(basedir, f"srt/{self.app}/report", public=True)

    def results_by_target(self, target):
        results = []
        for run in self.runs:
            for result in run.responses:
                if result.target.key == target.key:
                    results.append(result)
        return results


def as_json(obj):
    if isinstance(obj, list):
        return [as_json(o) for o in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "jsonable"):
        return obj.jsonable()
    else:
        return obj
