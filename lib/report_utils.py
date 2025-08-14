from datetime import datetime
import os
import pystache
import requests

from lib.file_cache_decorator import file_cached
from lib.utils import average_by_index
from lib.filestore import upload_dir
from nypl_py_utils.functions.log_helper import create_log

logger = create_log("S3")


def upload_pending_report(path, log, done=False):
    basedir = "/tmp/srt/pending-report"
    os.makedirs(basedir, exist_ok=True)
    template_vars = {
        "log": log,
        "build_time": datetime.now().strftime("%c"),
        "working": not done,
    }
    renderer = pystache.Renderer(search_dirs="./templates")
    html = renderer.render("{{>pending_report}}", template_vars)
    with open(f"{basedir}/index.html", "w") as f:
        f.write(html)
    upload_dir(basedir, f"srt/{path}/", public=True)


def normalize_run_data(results):
    scores = []
    elapsed = []
    elapsed_relative = []
    counts_relative = []
    max_elapsed = max([r.elapsed for r in results])
    max_count = max([r.count for r in results])

    for i, result in enumerate(results):
        scores.append(result.metric_score)
        elapsed.append(result.elapsed)
        elapsed_relative.append(result.elapsed / max_elapsed)
        count_relative = result.count / max_count if max_count > 0 else 0
        counts_relative.append(count_relative)

    return scores, elapsed, elapsed_relative, counts_relative


def normalize_overall_run_data(results):
    all_scores = []
    all_elapsed = []

    for result in results:
        scores, elapsed, elapsed_relative, counts = normalize_run_data(result)

        all_scores.append(scores)
        all_elapsed.append(elapsed)

    overall_scores = average_by_index(all_scores)
    overall_elapsed = average_by_index(all_elapsed)
    max_elapsed = max([avg_elapsed for avg_elapsed in overall_elapsed])
    overall_elapsed_relative = [elapsed / max_elapsed for elapsed in overall_elapsed]

    return overall_scores, overall_elapsed, overall_elapsed_relative


@file_cached
def basic_bib_metadata(bnum):
    doc = None
    try:
        url = f"https://platform.nypl.org/api/v0.1/discovery/resources/{bnum}"
        doc = requests.get(url).json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Requests error: {e}")
        return {"bnum": bnum, "missing": True}

    title = None
    author = None
    if len(doc.get("title", [])) > 0:
        title = doc["title"][0]
    if len(doc.get("creatorLiteral", [])) > 0:
        author = doc["creatorLiteral"][0]
    return {"bnum": bnum, "title": title, "author": author}
