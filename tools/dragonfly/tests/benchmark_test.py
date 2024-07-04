"""Tests for the benchmark module."""

from benchmark.validate import Validate


def test_validation_functions_existence():
    """Test that all expected validation functions exist in the Validate class."""
    # List of the expected validation method names
    expected_methods = {
        "validate_fact_retrieval",
        "validate_logical_reasoning",
        "validate_opinion_interpretation",
        "validate_language_understanding",
        "validate_long_form_answers",
        "validate_contextual_awareness",
        "validate_creative_problem_solving",
        "validate_negative_questions",
        "validate_summaries",
        "validate_procedural_questions",
        "validate_cause_effect",
        "validate_comparative_analysis",
        "validate_speculative_questions",
        "validate_translation",
    }

    # Check each method in the Validate class
    for method_name in expected_methods:
        assert hasattr(Validate, method_name), f"Missing method: {method_name}"
        assert callable(getattr(Validate, method_name)), f"Method {method_name} is not callable"

    # Get all attributes that are callable and should be considered as methods
    class_methods = {
        m for m in dir(Validate) if callable(getattr(Validate, m)) and not m.startswith("__")
    }

    # Check that there are no extra methods in the Validate class
    extra_methods = class_methods - expected_methods
    assert not extra_methods, f"Extra methods found: {extra_methods}"
