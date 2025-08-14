import pytest
from unittest.mock import MagicMock

from lib.models.run import Run


def test_run_for_path():
    mock_report = MagicMock()
    mock_report().app.return_value = "my-app"

    run = Run.for_path(mock_report, "./fixtures/run-1.json", "My description")

    assert run.base_dir == "./fixtures/run-1.json"
    assert run.commit_description == "My description"


def test_run_for_json():
    mock_report = MagicMock()
    mock_report().app.return_value = "my-app"

    run = Run.from_json(mock_report, {
        "commit_id": "commit id",
        "commit_description": "description",
        "commit_date": "2012-01-01",
        "previous_commot_id": "previous commit id",
        "run_date": "run date",
        "responses": []
    })

    assert run.commit_id == "commit id"


@pytest.fixture
def mock_app_config():
    return MagicMock()


def test_run_has_equivalent_scores_self(mock_app_config):
    mock_app_config.local_temp_path.return_value = "./tests/fixtures"

    run1 = Run.by_manifest_file(mock_app_config, "run-1")
    run2 = Run.by_manifest_file(mock_app_config, "run-1")

    equiv, rationale = run1.has_equivalent_scores(run2)
    assert equiv is True


def test_run_has_equivalent_scores_other(mock_app_config):
    mock_app_config.local_temp_path.return_value = "./tests/fixtures"

    run1 = Run.by_manifest_file(mock_app_config, "run-1")
    run2 = Run.by_manifest_file(mock_app_config, "run-2")

    equiv, rationale = run1.has_equivalent_scores(run2)
    assert equiv is False
