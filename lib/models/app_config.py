import csv
import json
import os
import yaml

from lib.utils import local_application_file
from lib.models.search_target import SearchTarget
from lib.utils import shell_exec
from nypl_py_utils.functions.log_helper import create_log


class AppConfigException(Exception):
    pass


class AppConfig:
    def __init__(self, app_name: str):
        self.app_name = app_name

        self._official_commits = None
        self._config = None

        self.logger = create_log(__name__)

    def config(self):
        if self._config is None:
            try:
                path = local_application_file(self.app_name, "config.yaml")
            except Exception:
                raise AppConfigException(f"Error fetching {self.app_name}/targets.yaml")

            with open(path) as f:
                self._config = yaml.safe_load_all(f)
        return self._config

    def load_targets(self, **kwargs):
        try:
            path = local_application_file(self.app_name, "targets.yaml")
        except Exception:
            raise AppConfigException(f"Error fetching {self.app_name}/targets.yaml")

        self.targets = SearchTarget.load_all_from(path)

        if kwargs.get("rows", None) is not None:
            self.targets = [self.targets[r] for r in kwargs["rows"]]
        return self.targets

    def official_commits(self):
        if self._official_commits is None:
            path = local_application_file(self.app_name, "commits.csv")
            with open(path) as f:
                self._official_commits = [row for row in csv.DictReader(f)]
        return self._official_commits

    def local_temp_path(self, folder=None):
        basedir = os.path.join(os.sep, "tmp", "srt", self.app_name)
        if folder is not None:
            return os.path.join(basedir, folder)
        return basedir

    def load_es_config(self, path: str, **kwargs):
        self.logger.info(f"Load config from {path}")

        outfile = "/tmp/es-config"
        shell_exec(
            "bash",
            os.path.join(self.local_config_path(), "get-config.sh"),
            path,
            outfile,
        )

        with open(outfile) as f:
            es_config = json.loads(f.read())
        os.remove(outfile)

        return es_config

    def local_config_path(self):
        return f"./applications/{self.app_name}"

    def jsonable(self):
        return {"app_name": self.app_name}

    @staticmethod
    def for_name(app_name: str):
        return AppConfig(app_name)
