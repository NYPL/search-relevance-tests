from datetime import datetime
import os
import pystache

from lib.models.run import Run
from lib.models.app_config import AppConfig
from lib.graphs import create_graph
from lib.utils import format_float
from lib.report_utils import normalize_run_data, normalize_overall_run_data
from lib.filestore import upload_dir
from nypl_py_utils.functions.log_helper import create_log


class Report:
    def __init__(self, app: str):
        self.app_config = AppConfig.for_name(app)

        self.runs = []

        self.logger = create_log(__name__)

    def jsonable(self):
        return {"app": self.app}

    def add_run(self, base_dir, description):
        run = Run.for_path(self, base_dir, description)
        self.runs.append(run)
        return run

    def previous_run_for(self, run, previous_runs):
        for previous_run in previous_runs:
            if run.commit_id == previous_run.commit_id:
                return previous_run

    def collect_data(self, **kwargs):
        previous_runs = self.load_runs_from_manifests()

        basedir = self.app_config.local_temp_path("manifests")
        stale_manifests = set(
            [
                run.manifest_file_path(basedir)
                for run in previous_runs
                if run.commit_id not in [r.commit_id for r in self.runs]
            ]
        )
        for path in stale_manifests:
            self.logger.info(
                f"  Consider removing stale run not found in commits.csv: {path}"
            )
            # TODO: This was deleting things too aggressively, so disabling for now:
            # os.remove(path)

        for ind, run in enumerate(self.runs):
            self.logger.info(f"Run {ind + 1} of {len(self.runs)}")

            previous_run = (
                None
                if kwargs.get("rebuild")
                else self.previous_run_for(run, previous_runs)
            )
            run.collect_data(previous_run)

    def save_manifests(self):
        self.logger.info("Saving and uploading manifests")
        basedir = self.app_config.local_temp_path("manifests")
        [run.save_manifest(basedir) for run in self.runs]

        upload_dir(
            basedir,
            f"srt/{self.app_config.app_name}/manifests",
            exclude=["local.json", "latest.json"],
        )

    def add_registered_runs(self):
        official_commit_runs = [
            Run.for_commit(self, c["commit"], c["description"])
            for c in self.app_config.official_commits()
        ]
        self.runs.extend(official_commit_runs)

    def load_runs_from_manifests(self, include_local=False, include_latest=False):
        self.runs = Run.all_from_manifests(
            self.app_config, include_local=include_local, include_latest=include_latest
        )
        return self.runs

    def build(self, folder_name="report", **kwargs):
        palette = {"red": "#920711", "blue": "#00838a", "orange": "#EC7B1F"}

        basedir = self.app_config.local_temp_path(folder_name)
        self.logger.info(f"Building report in {basedir}")

        os.makedirs(f"{basedir}/graphs", exist_ok=True)

        targets = self.app_config.load_targets()

        targets_with_runs = [
            {
                "target": target,
                "number": i + 1,
                "results": self.results_by_target(target),
            }
            for i, target in enumerate(targets)
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
            if len(scores) != len(self.runs):
                self.logger.error(
                    f"\nFound error in manifests: Expected {len(self.runs)} scores for target {target}; Found {len(scores)}. Exiting"
                )
                exit(1)

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

        official_report_url = "https://research-catalog-stats.s3.amazonaws.com/srt/discovery-api/report/index.html"
        alert = None
        if kwargs.get("include_local"):
            for run in self.runs:
                if run.is_local():
                    alert = (
                        f'This is a candidate search relevancy report for: "{run.commit_description}". '
                        f' The current <em>official</em> report <a href="{official_report_url}">'
                        "is here</a>."
                    )
        if kwargs.get("include_latest"):
            for run in self.runs:
                if run.is_latest():
                    alert = (
                        "This is a search relevancy report showing scoring differences between the "
                        f'<a href="{run.change_url()}">last official commit and `main`</a>.'
                    )

        template_vars = {
            "report_id": datetime.now(),
            "build_time": datetime.now().strftime("%c"),
            "colors": palette,
            "run_summary": as_json(run_summary),
            "targets": as_json(targets_with_runs),
            "alert": alert,
        }
        html = renderer.render("{{>report}}", template_vars)

        with open(f"{basedir}/index.html", "w") as f:
            f.write(html)

        if kwargs.get("persist_to_s3", True):
            upload_dir(
                basedir, f"srt/{self.app_config.app_name}/{folder_name}/", public=True
            )

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
