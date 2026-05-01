import json

from lib.report_utils import (
    basic_bib_metadata,
    normalize_run_data,
    normalize_overall_run_data,
)
from lib.models.search_target_response import SearchTargetResponse


def test_normalize_run_data():
    results = [
        SearchTargetResponse(
            elapsed=100, count=100, response={"metric_score": 0.5}, target=None
        ),
        SearchTargetResponse(
            elapsed=400, count=125, response={"metric_score": 0.75}, target=None
        ),
    ]
    scores, elapsed, elapsed_relative, counts_relative = normalize_run_data(results)
    assert scores == [0.5, 0.75]
    assert elapsed_relative == [0.25, 1]
    assert counts_relative == [0.80, 1]


def test_normalize_overall_run_data():
    results = [
        [
            SearchTargetResponse(
                elapsed=100, count=100, response={"metric_score": 0.5}, target=None
            ),
            SearchTargetResponse(
                elapsed=400, count=125, response={"metric_score": 0.75}, target=None
            ),
        ],
        [
            SearchTargetResponse(
                elapsed=200, count=100, response={"metric_score": 0.7}, target=None
            ),
            SearchTargetResponse(
                elapsed=600, count=125, response={"metric_score": 0.85}, target=None
            ),
        ],
    ]

    scores, elapsed, elapsed_relative = normalize_overall_run_data(results)

    assert scores == [0.6, 0.8]
    assert elapsed == [150, 500]
    assert elapsed_relative == [0.3, 1]


def test_basic_bib_metadata(requests_mock):
    bnum = "b12345"
    url = f"https://platform.nypl.org/api/v0.1/discovery/resources/{bnum}"
    record = {"uri": bnum, "title": ["Item Title"], "creatorLiteral": ["Item Author"]}
    requests_mock.get(url, text=json.dumps(record))

    metadata = basic_bib_metadata(bnum, no_cache=True)
    assert metadata["title"] == "Item Title"
    assert metadata["author"] == "Item Author"
