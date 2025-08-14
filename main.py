import argparse
import json
import os
import sys
import traceback

from lib.models.app_config import AppConfig, AppConfigException
from lib.models.run import Run
from lib.models.report import Report
from lib.utils import shell_exec, git_active_branch, prompt_with_prefill
from lib.filestore import upload_dir
from lib.report_utils import upload_pending_report
from nypl_py_utils.functions.log_helper import create_log
from nypl_py_utils.functions.config_helper import load_env_file
from lib.lambda_utils import validate_webhook, WebhookException, lambda_error


load_env_file(os.environ.get('ENVIRONMENT', "qa"), 'config/{}.yaml')
logger = create_log('main')


def parse_args():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Run a collection of rank-eval calls against configured app",
        epilog="Text at the bottom of help",
    )

    applications = os.listdir("./applications")

    parser.add_argument("app", choices=applications)
    parser.add_argument(
        "command", choices=["test-local", "test-all", "test-latest", "rebuild-report", "build", "lambda-event"]
    )
    parser.add_argument("-t", "--targets", default="targets.yaml")
    parser.add_argument(
        "--no-persist-to-s3", dest="persist_to_s3", action="store_false"
    )
    parser.add_argument(
        "--no-rebuild-graphs", dest="rebuild_graphs", action="store_false"
    )
    parser.add_argument(
        "--include-local", dest="include_local", action="store_true"
    )
    parser.add_argument(
        "--include-latest", dest="include_latest", action="store_true"
    )
    parser.add_argument(
        "--rebuild", action="store_true"
    )
    parser.add_argument(
        "--publish", action="store_true"
    )
    parser.add_argument("--rows")
    parser.add_argument("--envfile")
    parser.add_argument("--appdir")
    parser.add_argument("--description")
    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument("--event-file", dest="event_file")

    return parser.parse_args()


def lambda_handler(event, context):
    if event.get("body") and event.get("headers"):
        try:
            validate_webhook(event)

        except WebhookException as e:
            return lambda_error(403, e)

        try:
            body = json.loads(event["body"])
            app = body["repository"]["name"]
            # FIXME: Temporary hack to test pushes to this repo:
            if app == "search-relevance-tests":
                app = "discovery-api"

            logger.info(f"Webhook validated; Proceeding with test-latest for {app}")

            return run_test_latest(app=app)
        except AppConfigException as e:
            return lambda_error(400, e)
        except Exception as e:
            return lambda_error(500, e)

    logger.info(f"Handling event: {event}")

    app = event.get("app")
    if app is None:
        raise "app is required"

    command = event.get("command")
    if command == "test-local":
        logger.error("No support for command=test-local in a Lambda environment")
        return False

    elif command == "test-latest":
        run_test_latest(app=app)

    elif command == "test-all":
        run_test_all(app=app)
        rebuild_report(app=app)

    elif command == "rebuild-report":
        rebuild_report(app=app)

    else:
        logger.error(f"Unknown command: {command}")
        return False

    return True


def run_test_local(**kwargs):
    app_config = AppConfig.for_name(kwargs["app"])

    app_config.load_targets(rows=kwargs.get("rows", None))

    if kwargs["appdir"] is None:
        logger.error("--appdir PATH required")
        exit()
    if kwargs["description"] is None:
        logger.error("--description DESC required")
        exit()

    logger.info(f"Running targets against code in {kwargs['appdir']}")
    run = Run.for_path(app_config, kwargs["appdir"], kwargs["description"], file_key="local")
    run.collect_data()
    run.save_manifest()


def run_test_all(**kwargs):
    app_config = AppConfig.for_name(kwargs["app"])
    app_config.load_targets(rows=kwargs.get("rows", None))

    runs = [
        Run.for_commit(app_config, c["commit"], c["description"])
        for c in app_config.official_commits()
    ]
    for run in runs:
        run.collect_data(rebuild=kwargs.get('rebuild'))
        run.save_manifest()
    upload_dir(
        app_config.local_temp_path("manifests"),
        f"srt/{app_config.app_name}/manifests",
        exclude=["local.json", "latest.json"]
    )
    logger.info("Done")


def run_test_latest(**kwargs):
    app_config = AppConfig.for_name(kwargs["app"])
    app_config.load_targets(rows=kwargs.get("rows", None))

    log = []

    try:
        def log_progress(message, done=False):
            logger.info(message)
            log.append(message)
            upload_pending_report(f"{app_config.app_name}/report-latest", log, done)

        checkout_base_dir = app_config.local_temp_path("app")
        run = Run.for_path(app_config, checkout_base_dir, 'Latest main branch', file_key="latest")
        last_run = Run.all_from_manifests(app_config)[-1]

        git_url = f"https://github.com/NYPL/discovery-api/compare/{last_run.commit_id}...{run.get_commit_id()}"
        log_progress(f"Building 'latest' report for <a href='{git_url}'>changes to main</a>")

        log_progress("Initializing app")
        run.initialize_app(use_cache=False, commit_id="HEAD")

        log_progress("Collecting data")
        run.collect_data()

        log_progress("Comparing scores to last run")
        equivalent, explanation = last_run.has_equivalent_scores(run)

        if equivalent:
            log_progress("No scores changed in main.", True)
        else:
            logger.info(f'Scores changed: {explanation}')
            run.save_manifest()
            rebuild_report(
                app=args.app,
                include_latest=True,
                rebuild_graphs=args.rebuild_graphs,
                persist_to_s3=args.persist_to_s3,
                folder_name="report-latest",
            )
    except Exception as e:
        log_progress(f"Error: {str(e)}", True)
        traceback.print_exc()


def report_folder_name(folder_name="report", include_local=False, include_latest=False):
    return folder_name


def rebuild_report(**kwargs):
    report = Report(app=kwargs["app"])
    report.load_runs_from_manifests(
        include_local=kwargs.get("include_local"),
        include_latest=kwargs.get("include_latest"),
    )

    default_folder_name = "report"
    if kwargs.get("include_local", False):
        default_folder_name = "report-local"
    if kwargs.get("include_latest", False):
        default_folder_name = "report-latest"
    folder_name = kwargs.get("folder_name", default_folder_name)

    report.build(
        rebuild_graphs=kwargs.get("rebuild_graphs", True),
        persist_to_s3=kwargs.get("persist_to_s3", True),
        folder_name=folder_name,
        include_local=kwargs.get("include_local"),
        include_latest=kwargs.get("include_latest"),
    )


def build_application_versions(**kwargs):
    logger.info("Building application versions")

    report = Report(app=kwargs["app"])
    report.add_registered_runs()

    for run in report.runs:
        run.initialize_app(use_cache=False)
        run.package_app()


# Detect invocation via CLI versus in a Lambda environment.
# If filename is other than main.py, must be Lambda environment:
if len(sys.argv) > 0 and "main.py" in sys.argv[0]:
    args = parse_args()

    if args.app and args.command:
        rows = None
        if args.rows is not None:
            rows = [int(r) for r in args.rows.split(",")]

        if args.command == "test-local":
            run_test_local(app=args.app, rows=rows, appdir=args.appdir, description=args.description)

            app_config = AppConfig.for_name(args.app)
            folder_name = "report-latest"

            # If publishing report to S3, get a more approrpiate folder_name:
            if args.publish:
                branch = git_active_branch(args.appdir)
                print("Choose a filename to publish local to S3")
                folder_name = prompt_with_prefill("Enter filename for published report: ", f"report-{branch}")

                s3_prefix = f"srt/{args.app}/{folder_name}"
                report_url = f"https://research-catalog-stats.s3.amazonaws.com/{s3_prefix}/index.html"

            rebuild_report(
                app=args.app,
                persist_to_s3=args.publish,
                include_local=True,
                rebuild_graphs=args.rebuild_graphs,
                folder_name=folder_name,
            )
            shell_exec("open", report_url)

        if args.command == "test-all":
            run_test_all(app=args.app, rows=rows, rebuild=args.rebuild)
        if args.command == "test-latest":
            run_test_latest(app=args.app, rows=rows)
        if args.command == "rebuild-report":
            rebuild_report(
                app=args.app,
                persist_to_s3=args.persist_to_s3,
                rebuild_graphs=args.rebuild_graphs,
                include_local=args.include_local,
                include_latest=args.include_latest,
            )
        if args.command == "build":
            build_application_versions(app=args.app)

        if args.command == "lambda-event":
            event = None
            with open(args.event_file, 'r') as f:
                event = json.load(f)
            response = lambda_handler(event, {})
