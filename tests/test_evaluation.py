"""Tests for Milestone 8: Golden Evaluation Benchmark Execution."""
import pytest
from scripts.evaluate_golden_set import run_golden_evaluation


def test_golden_set_evaluation():
    summary = run_golden_evaluation()
    assert summary["total_test_cases"] == 20
    assert summary["overall_accuracy"] >= 0.85
    assert summary["adversarial_cases"] == 5
    assert summary["adversarial_robustness_rate"] == 1.0
    assert summary["evaluation_band"] == "Distinction (Level 4)"
