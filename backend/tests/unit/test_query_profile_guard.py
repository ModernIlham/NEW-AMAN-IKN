"""A profile must inspect the winning plan of an owned synthetic dataset."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("asset_query_profile", Path(__file__).resolve().parents[3] / "scripts/profile_asset_reads.py")
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


@pytest.mark.parametrize("url,database", [("mongodb://production.example", "aman_ci_12345678"),
    ("mongodb://127.0.0.1", "production"), ("mongodb://user:password@localhost", "aman_ci_12345678"),
    ("mongodb://localhost/?directConnection=true", "aman_ci_12345678")])
def test_profile_rejects_nonlocal_or_unowned_target(url, database):
    with pytest.raises(ValueError):
        profile.validate_target(url, database, {"database": database, "run_id": "12345678", "asset_count": 10000})


def test_profile_manifest_must_match_database():
    with pytest.raises(ValueError):
        profile.validate_target("mongodb://localhost", "aman_ci_12345678", {"database": "aman_ci_other", "run_id": "12345678", "asset_count": 10000})


def test_profile_does_not_claim_rejected_or_original_pipeline_sort_executed():
    explanation = {"queryPlanner": {"winningPlan": {"stage": "IXSCAN", "indexName": "cover"},
        "rejectedPlans": [{"stage": "SORT", "indexName": "unused"}]},
        "executionStats": {"totalDocsExamined": 50, "totalKeysExamined": 50},
        "command": {"pipeline": [{"$sort": {"created_at": -1}}]}}
    result = profile.summarize_explain(explanation)
    assert result["indexes"] == ["cover"]
    assert not result["in_memory_sort"]
    assert result["docs_examined"] == result["keys_examined"] == 50
    explanation["stages"] = [{"$sort": {"sortKey": {"price": 1}}, "usedDisk": True}]
    result = profile.summarize_explain(explanation)
    assert result["in_memory_sort"] and result["used_disk"]
