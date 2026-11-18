"""Tests for Data Assets A, B, C, D Integrity."""
import json
from pathlib import Path
import pytest
from app.config.settings import get_settings


def test_asset_a_corpus_integrity():
    settings = get_settings()
    corpus_md = settings.DATA_DIR / "corpus" / "markdown"
    assert corpus_md.exists()
    md_files = list(corpus_md.glob("*.md"))
    assert len(md_files) == 13

    # Check 5 policies and 8 manuals
    slugs = {f.stem for f in md_files}
    assert "lockout-tagout" in slugs
    assert "permit-to-work" in slugs
    assert "spares-procurement" in slugs
    assert "alarm-response" in slugs
    assert "maintenance-planning" in slugs
    assert "manual-air-comp" in slugs
    assert "manual-hyd-press" in slugs


def test_asset_b_intake_records_integrity():
    settings = get_settings()
    records_file = settings.DATA_DIR / "intake" / "records.jsonl"
    assert records_file.exists()

    records = []
    with open(records_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    assert len(records) == 200
    # Verify ground truth preserved on all records
    assert all("ground_truth" in r for r in records)


def test_asset_c_mock_api_tables_integrity():
    settings = get_settings()
    mock_dir = settings.DATA_DIR / "mock_api"
    assert mock_dir.exists()

    expected_tables = [
        "asset_classes", "asset_criticality", "criticality_matrix",
        "inventory", "part_suppliers", "purchase_orders", "suppliers",
        "technicians", "technician_calendar", "telemetry", "telemetry_pressure",
        "work_orders", "work_order_details",
    ]
    for tbl in expected_tables:
        csv_file = mock_dir / f"{tbl}.csv"
        json_file = mock_dir / f"{tbl}.json"
        assert csv_file.exists(), f"Missing {csv_file}"
        assert json_file.exists(), f"Missing {json_file}"


def test_asset_d_golden_set_integrity():
    settings = get_settings()
    golden_file = settings.DATA_DIR / "eval" / "golden_set.json"
    assert golden_file.exists()

    with open(golden_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) == 20
    # Verify the 5 adversarial cases PLANTGUARD-EV-901 to 905
    adversarial_ids = {"PLANTGUARD-EV-901", "PLANTGUARD-EV-902", "PLANTGUARD-EV-903", "PLANTGUARD-EV-904", "PLANTGUARD-EV-905"}
    found_ids = {c["id"] for c in cases}
    assert adversarial_ids.issubset(found_ids)
