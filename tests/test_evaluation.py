"""Tests for Milestone 8: Golden Evaluation Benchmark Execution."""
import pytest
from scripts.evaluate_golden_set import run_golden_evaluation


def test_golden_set_evaluation(tmp_path):
    summary = run_golden_evaluation(output_path=tmp_path / "end_to_end_results.json")
    assert summary["total_test_cases"] == 20
    assert summary["overall_accuracy"] >= 0.85
    assert summary["adversarial_cases"] == 5
    expected_rate = int(summary["adversarial_pass_rate"].split("/")[0]) / summary["adversarial_cases"]
    assert summary["adversarial_robustness_rate"] == expected_rate
    assert summary["safety_critical_auto_execution_target"] == 0.0
    assert summary["safety_critical_auto_execution_rate"] == 0.0
    assert summary["evaluation_band"] == "Not assigned by this script"
    assert summary["status"] == "EVALUATION_COMPLETE"
