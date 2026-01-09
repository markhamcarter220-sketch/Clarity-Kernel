"""
Tests for deterministic w-counting and fraud detection.

This test suite proves that w-counting is mechanical and ungameable by testing:
1. Variable bundling detection (combining multiple concerns into one variable)
2. Probabilistic collapse detection (guessing values to reduce w)
3. Material misclassification detection (marking safety-critical vars as non-material)
4. Correct w-counting with honest variable classification
"""

import pytest
from clarity_kernel import (
    Variable,
    WCountingFraudViolation,
    detect_variable_bundling,
    detect_probabilistic_collapse,
    validate_material_classification,
    validate_complexity,
)


# ============================================================================
# VARIABLE BUNDLING DETECTION
# ============================================================================

def test_bundling_detected_in_variable_name_with_and():
    """Variable names containing '_and_' should be flagged as bundling."""
    variables = [
        Variable("dosage_and_route", resolved=False, material=True, value=None),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is not None
    assert fraud.fraud_type == "variable_bundling"
    assert "dosage_and_route" in fraud.evidence["variable_name"]


def test_bundling_detected_in_variable_name_with_or():
    """Variable names containing '_or_' should be flagged as bundling."""
    variables = [
        Variable("read_or_write", resolved=False, material=True, value=None),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is not None
    assert fraud.fraud_type == "variable_bundling"


def test_bundling_detected_with_config_suffix():
    """Variable names like 'patient_config' suggest bundling."""
    variables = [
        Variable("patient_config", resolved=False, material=True, value=None),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is not None
    assert fraud.fraud_type == "variable_bundling"


def test_bundling_detected_with_options_suffix():
    """Variable names like 'execution_options' suggest bundling."""
    variables = [
        Variable("execution_options", resolved=False, material=True, value=None),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is not None
    assert fraud.fraud_type == "variable_bundling"


def test_generic_variable_name_detected():
    """Overly generic names like 'config', 'data', 'options' are flagged."""
    generic_names = ["config", "data", "info", "options", "params", "settings"]

    for name in generic_names:
        variables = [
            Variable(name, resolved=False, material=True, value=None),
        ]

        fraud = detect_variable_bundling(variables)

        assert fraud is not None, f"Generic name '{name}' should be flagged"
        assert fraud.fraud_type == "generic_variable_name"


def test_generic_name_allowed_if_resolved_or_nonmaterial():
    """Generic names are OK if the variable is resolved or non-material."""
    # Resolved generic variable - OK
    variables1 = [
        Variable("config", resolved=True, material=True, value={"key": "value"}),
    ]
    fraud1 = detect_variable_bundling(variables1)
    # Note: This might still be flagged as dict_bundling if dict has multiple keys
    # But it won't be flagged as generic_variable_name

    # Non-material generic variable - OK
    variables2 = [
        Variable("config", resolved=False, material=False, value=None),
    ]
    fraud2 = detect_variable_bundling(variables2)
    assert fraud2 is None  # Non-material variables don't trigger generic name check


def test_bundling_detected_in_dict_value():
    """Resolved variables with multi-key dicts should be flagged."""
    variables = [
        Variable(
            "patient_data",
            resolved=True,
            material=True,
            value={"age": 65, "weight": 70, "blood_type": "A+"}
        ),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is not None
    assert fraud.fraud_type == "dict_bundling"
    assert fraud.evidence["num_keys"] == 3


def test_single_key_dict_not_flagged():
    """Dicts with only one key are not bundling."""
    variables = [
        Variable(
            "patient_id",
            resolved=True,
            material=True,
            value={"id": "12345"}
        ),
    ]

    fraud = detect_variable_bundling(variables)

    # Should not be flagged as dict_bundling (only 1 key)
    # But might be flagged for other reasons - check specifically for dict_bundling
    if fraud is not None:
        assert fraud.fraud_type != "dict_bundling"


def test_well_named_single_purpose_variables_pass():
    """Well-named, single-purpose variables should not be flagged."""
    variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_weight_kg", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=True, material=True, value="aspirin"),
        Variable("file_path", resolved=True, material=True, value="/etc/config.yaml"),
    ]

    fraud = detect_variable_bundling(variables)

    assert fraud is None  # No bundling detected


# ============================================================================
# PROBABILISTIC COLLAPSE DETECTION
# ============================================================================

def test_probabilistic_collapse_detected():
    """Guessing values to reduce w should be detected."""
    # Before: 3 unresolved material variables (w=3)
    variables_before = [
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=False, material=True, value=None),
    ]

    # After: Suddenly 2 are resolved (w=1) - SUSPICIOUS
    variables_after = [
        Variable("dosage", resolved=True, material=True, value=50),  # Guessed!
        Variable("route", resolved=True, material=True, value="oral"),  # Guessed!
        Variable("patient_id", resolved=False, material=True, value=None),
    ]

    fraud = detect_probabilistic_collapse(variables_before, variables_after)

    assert fraud is not None
    assert fraud.fraud_type == "probabilistic_collapse"
    assert fraud.evidence["actual_w"] == 3
    assert fraud.evidence["reported_w"] == 1
    assert len(fraud.evidence["collapsed_variables"]) == 2


def test_legitimate_resolution_not_flagged():
    """If variables don't change status, no collapse detected."""
    variables_before = [
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=True, material=True, value="12345"),
    ]

    variables_after = [
        Variable("dosage", resolved=False, material=True, value=None),  # Still unresolved
        Variable("patient_id", resolved=True, material=True, value="12345"),  # Still resolved
    ]

    fraud = detect_probabilistic_collapse(variables_before, variables_after)

    assert fraud is None


def test_nonmaterial_resolution_not_flagged():
    """Resolving non-material variables is OK (they don't contribute to w)."""
    variables_before = [
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("request_id", resolved=False, material=False, value=None),
    ]

    variables_after = [
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("request_id", resolved=True, material=False, value="req_123"),  # OK to resolve
    ]

    fraud = detect_probabilistic_collapse(variables_before, variables_after)

    assert fraud is None  # Non-material variables don't trigger collapse detection


# ============================================================================
# MATERIAL MISCLASSIFICATION DETECTION
# ============================================================================

def test_safety_critical_variable_marked_nonmaterial_detected():
    """Safety-critical variables marked non-material should be flagged."""
    variables = [
        Variable("dosage_mg", resolved=False, material=False, value=None),  # FRAUD
        Variable("patient_weight", resolved=False, material=False, value=None),  # FRAUD
    ]

    safety_critical = {"dosage_mg", "patient_weight"}

    with pytest.raises(WCountingFraudViolation) as exc_info:
        validate_material_classification(variables, safety_critical)

    assert exc_info.value.fraud_type == "material_misclassification"
    assert "dosage_mg" in exc_info.value.evidence["variable_name"]


def test_material_classification_passes_when_correct():
    """Correctly classified variables should pass validation."""
    variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),  # Correct
        Variable("patient_weight", resolved=False, material=True, value=None),  # Correct
        Variable("request_id", resolved=False, material=False, value=None),  # Correct (non-critical)
    ]

    safety_critical = {"dosage_mg", "patient_weight"}

    # Should not raise
    validate_material_classification(variables, safety_critical)


def test_material_classification_no_check_if_no_safety_critical_set():
    """If no safety-critical names provided, validation is skipped."""
    variables = [
        Variable("anything", resolved=False, material=False, value=None),
    ]

    # Should not raise - no safety critical names to check
    validate_material_classification(variables, safety_critical_names=None)


# ============================================================================
# CORRECT W-COUNTING WITH HONEST CLASSIFICATION
# ============================================================================

def test_correct_w_counting_with_honest_variables():
    """W should be counted correctly with honestly classified variables."""
    variables = [
        # 3 unresolved material variables
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=False, material=True, value=None),
        # 1 resolved material variable (doesn't count toward w)
        Variable("drug_name", resolved=True, material=True, value="aspirin"),
        # 2 non-material variables (don't count toward w)
        Variable("request_id", resolved=False, material=False, value=None),
        Variable("log_level", resolved=True, material=False, value="INFO"),
    ]

    # Measure w
    w = validate_complexity(variables, max_width=3)

    assert w == 3  # Exactly 3 unresolved material variables


def test_w_counting_stops_at_limit():
    """W-counting should enforce w ≤ 3."""
    variables = [
        Variable("var1", resolved=False, material=True, value=None),
        Variable("var2", resolved=False, material=True, value=None),
        Variable("var3", resolved=False, material=True, value=None),
        Variable("var4", resolved=False, material=True, value=None),  # Exceeds limit
    ]

    # Should raise ComplexityInvariantViolation
    from clarity_kernel import ComplexityInvariantViolation

    with pytest.raises(ComplexityInvariantViolation) as exc_info:
        validate_complexity(variables, max_width=3)

    assert exc_info.value.measured_w == 4
    assert len(exc_info.value.unresolved_variables) == 4


def test_w_zero_with_all_resolved():
    """W should be 0 if all material variables are resolved."""
    variables = [
        Variable("dosage", resolved=True, material=True, value=50),
        Variable("route", resolved=True, material=True, value="oral"),
        Variable("patient_id", resolved=True, material=True, value="12345"),
    ]

    w = validate_complexity(variables, max_width=3)

    assert w == 0


def test_w_zero_with_all_nonmaterial():
    """W should be 0 if all variables are non-material (even if unresolved)."""
    variables = [
        Variable("request_id", resolved=False, material=False, value=None),
        Variable("log_level", resolved=False, material=False, value=None),
        Variable("cache_ttl", resolved=False, material=False, value=None),
    ]

    w = validate_complexity(variables, max_width=3)

    assert w == 0


# ============================================================================
# INTEGRATED FRAUD DETECTION EXAMPLES
# ============================================================================

def test_gaming_w_through_bundling_example():
    """
    Fraudulent example: Trying to pass w≤3 by bundling.

    Actual concerns: dosage, route, drug_name, patient_id (w=4)
    Fraudulent approach: Bundle into "patient_config" (w=1)
    """
    # Fraudulent variables - bundling
    fraudulent_variables = [
        Variable(
            "patient_config",  # Bundles multiple concerns
            resolved=False,
            material=True,
            value=None
        ),
    ]

    fraud = detect_variable_bundling(fraudulent_variables)

    assert fraud is not None
    assert fraud.fraud_type == "variable_bundling"

    # Correct approach - separate variables
    correct_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("administration_route", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=False, material=True, value=None),
    ]

    # This would correctly report w=4 and trigger STOP
    from clarity_kernel import ComplexityInvariantViolation

    with pytest.raises(ComplexityInvariantViolation):
        validate_complexity(correct_variables, max_width=3)


def test_gaming_w_through_misclassification_example():
    """
    Fraudulent example: Trying to pass w≤3 by marking critical vars non-material.

    Actual material variables: dosage, route, drug_name, patient_id (w=4)
    Fraudulent approach: Mark drug_name and patient_id as non-material (w=2)
    """
    # Fraudulent variables - misclassification
    fraudulent_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=False, value=None),  # FRAUD
        Variable("patient_id", resolved=False, material=False, value=None),  # FRAUD
    ]

    # Define safety-critical names
    safety_critical = {"dosage_mg", "route", "drug_name", "patient_id"}

    # Should detect fraud
    with pytest.raises(WCountingFraudViolation) as exc_info:
        validate_material_classification(fraudulent_variables, safety_critical)

    assert exc_info.value.fraud_type == "material_misclassification"


def test_gaming_w_through_probabilistic_collapse_example():
    """
    Fraudulent example: Trying to reduce w by guessing values.

    Initial state: dosage, route, drug (w=3)
    Fraudulent approach: Guess dosage=50, route="oral" → w=1
    """
    variables_before = [
        Variable("dosage", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("drug", resolved=False, material=True, value=None),
    ]

    # Fraudulent collapse - guessed values
    variables_after = [
        Variable("dosage", resolved=True, material=True, value=50),  # GUESSED
        Variable("route", resolved=True, material=True, value="oral"),  # GUESSED
        Variable("drug", resolved=False, material=True, value=None),
    ]

    fraud = detect_probabilistic_collapse(variables_before, variables_after)

    assert fraud is not None
    assert fraud.fraud_type == "probabilistic_collapse"
    assert fraud.evidence["actual_w"] == 3
    assert fraud.evidence["reported_w"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
