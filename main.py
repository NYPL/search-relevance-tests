import sys
import argparse
import os

from lib.models.report import Report


def parse_args():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Run a collection of rank-eval calls against configured app",
        epilog="Text at the bottom of help",
    )

    applications = os.listdir("./applications")

    parser.add_argument("app", choices=applications)
    parser.add_argument(
        "command", choices=["current", "all", "rebuild-report", "build"]
    )
    parser.add_argument("-t", "--targets", default="targets.yaml")
    parser.add_argument(
        "--no-persist-to-s3", dest="persist_to_s3", action="store_false"
    )
    parser.add_argument(
        "--no-rebuild-graphs", dest="rebuild_graphs", action="store_false"
    )
    parser.add_argument(
        "--rebuild", action="store_true"
    )
    parser.add_argument("--rows")
    parser.add_argument("--envfile")
    parser.add_argument("--appdir")
    parser.add_argument("--description")
    parser.add_argument("-v", "--verbose", action="store_true")

    return parser.parse_args()


def run_current(**kwargs):
    report = Report(kwargs["app"])

    report.load_targets(rows=kwargs.get("rows", None))

    if kwargs["appdir"] is None:
        print("--appdir PATH required")
        exit()
    if kwargs["description"] is None:
        print("--description DESC required")
        exit()

    print(f"Running targets against code in {kwargs['appdir']}")
    report.add_run(kwargs["appdir"], kwargs["description"])
    report.collect_data()
    report.save_manifests()


def run_all(**kwargs):
    report = Report(kwargs["app"])
    report.load_targets(rows=kwargs.get("rows", None))

    report.add_registered_runs()
    report.collect_data(rebuild=kwargs.get('rebuild'))
    report.save_manifests()
    print("Done")


def rebuild_report(**kwargs):
    report = Report(app=kwargs["app"])
    report.load_from_manifests()
    report.build(
        rebuild_graphs=kwargs.get("rebuild_graphs", True),
        persist_to_s3=kwargs.get("persist_to_s3"),
    )


def build_application_versions(**kwargs):
    print("Building application versions")

    report = Report(app=kwargs["app"])
    report.add_registered_runs()

    for run in report.runs:
        run.initialize_app(use_cache=False)
        run.package_app()


def lambda_handler(event, context):
    print(f"Handling event: {event}")
    app = event.get("app")
    if app is None:
        raise "app is required"

    command = event.get("command")
    if command == "current":
        print("No support for command=current in a Lambda environment")
        return False

    elif command == "all":
        run_all(app=app)
        rebuild_report(app=app)

    elif command == "rebuild-report":
        rebuild_report(app=app)

    else:
        print(f"Unknown command: {command}")
        return False

    return True


# Detect invocation via CLI versus in a Lambda environment.
# If filename is other than main.py, must be Lambda environment:
if len(sys.argv) > 0 and "main.py" in sys.argv[0]:
    args = parse_args()

    if args.app and args.command:
        rows = None
        if args.rows is not None:
            rows = [int(r) for r in args.rows.split(",")]

        if args.command == "current":
            run_current(app=args.app, rows=rows, appdir=args.appdir, description=args.description)
        if args.command == "all":
            run_all(app=args.app, rows=rows, rebuild=args.rebuild)
        if args.command == "rebuild-report":
            print(f"persist? {args.persist_to_s3}")
            rebuild_report(app=args.app, persist_to_s3=args.persist_to_s3, rebuild_graphs=args.rebuild_graphs)
        if args.command == "build":
            build_application_versions(app=args.app)
