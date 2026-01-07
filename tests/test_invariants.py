"""
Test Suite for Clarity Kernel Hard Invariants

Tests all seven hard invariants (I-1 through I-7) to ensure they:
1. Raise exceptions on violations (no warnings)
2. Pass when conditions are satisfied
3. Provide correct context in exceptions
"""

import pytest
from clarity_kernel.invariants import (
    Variable,
    AuthorityToken,
    validate_clarity,
    validate_authority,
    validate_attention,
    validate_truth,
    validate_logging,
    validate_silence,
    validate_complexity,
    ClarityInvariantViolation,
    AuthorityInvariantViolation,
    AttentionInvariantViolation,
    TruthInvariantViolation,
    LoggingInvariantViolation,
    SilenceInvariantViolation,
    ComplexityInvariantViolation,
    get_all_invariant_ids,
    is_invariant_satisfied,
)


# ============================================================================
# I-1: CLARITY INVARIANT TESTS
# ============================================================================


def test_i1_clarity_passes_when_all_defined():
    """I-1 should pass when all required elements are defined."""
    validate_clarity(
        required_definitions={"threshold": 10, "mode": "safe"},
        required_thresholds={"max_w": 3, "timeout": 30},
        required_constraints=["w <= 3", "authority present"]
    )
    # No exception = pass


def test_i1_clarity_fails_on_undefined_definition():
    """I-1 should raise exception when definition is None."""
    with pytest.raises(ClarityInvariantViolation) as exc_info:
        validate_clarity(
            required_definitions={"threshold": None},
            required_thresholds={},
            required_constraints=[]
        )
    assert "definition:threshold" in exc_info.value.ambiguous_elements
    assert exc_info.value.invariant_id == "I-1"


def test_i1_clarity_fails_on_empty_definition():
    """I-1 should raise exception when definition is empty string."""
    with pytest.raises(ClarityInvariantViolation) as exc_info:
        validate_clarity(
            required_definitions={"mode": ""},
            required_thresholds={},
            required_constraints=[]
        )
    assert "definition:mode" in exc_info.value.ambiguous_elements


def test_i1_clarity_fails_on_undefined_threshold():
    """I-1 should raise exception when threshold is None."""
    with pytest.raises(ClarityInvariantViolation) as exc_info:
        validate_clarity(
            required_definitions={},
            required_thresholds={"max_w": None},
            required_constraints=[]
        )
    assert "threshold:max_w" in exc_info.value.ambiguous_elements


def test_i1_clarity_fails_on_empty_constraint():
    """I-1 should raise exception when constraint is empty."""
    with pytest.raises(ClarityInvariantViolation) as exc_info:
        validate_clarity(
            required_definitions={},
            required_thresholds={},
            required_constraints=[""]
        )
    assert len(exc_info.value.ambiguous_elements) > 0


def test_i1_clarity_reports_multiple_violations():
    """I-1 should report all ambiguous elements."""
    with pytest.raises(ClarityInvariantViolation) as exc_info:
        validate_clarity(
            required_definitions={"a": None, "b": ""},
            required_thresholds={"t1": None},
            required_constraints=[""]
        )
    assert len(exc_info.value.ambiguous_elements) >= 3


# ============================================================================
# I-2: AUTHORITY INVARIANT TESTS
# ============================================================================


def test_i2_authority_passes_with_valid_token():
    """I-2 should pass when authority is explicit and verifiable."""
    authority = AuthorityToken(
        source="human_operator_001",
        verifiable=True,
        scope="deploy_production"
    )
    validate_authority(authority, required_scope="deploy_production")
    # No exception = pass


def test_i2_authority_fails_when_none():
    """I-2 should raise exception when authority is None."""
    with pytest.raises(AuthorityInvariantViolation) as exc_info:
        validate_authority(None, required_scope="execute")
    assert exc_info.value.invariant_id == "I-2"
    assert exc_info.value.required_authority == "execute"


def test_i2_authority_fails_when_not_verifiable():
    """I-2 should raise exception when authority is not verifiable."""
    authority = AuthorityToken(
        source="unknown",
        verifiable=False,
        scope="execute"
    )
    with pytest.raises(AuthorityInvariantViolation) as exc_info:
        validate_authority(authority, required_scope="execute")
    assert "not verifiable" in str(exc_info.value)


def test_i2_authority_fails_on_scope_mismatch():
    """I-2 should raise exception when authority scope doesn't match."""
    authority = AuthorityToken(
        source="operator",
        verifiable=True,
        scope="read_only"
    )
    with pytest.raises(AuthorityInvariantViolation) as exc_info:
        validate_authority(authority, required_scope="write_data")
    assert "scope mismatch" in str(exc_info.value).lower()


# ============================================================================
# I-3: ATTENTION INVARIANT TESTS
# ============================================================================


def test_i3_attention_passes_when_not_required():
    """I-3 should pass when continuous attention is not required."""
    validate_attention(
        requires_continuous_attention=False,
        attention_available=False,
        harm_scenario="none"
    )
    # No exception = pass


def test_i3_attention_passes_when_required_and_available():
    """I-3 should pass when continuous attention is both required and available."""
    validate_attention(
        requires_continuous_attention=True,
        attention_available=True,
        harm_scenario="potential data loss"
    )
    # No exception = pass


def test_i3_attention_fails_when_required_but_unavailable():
    """I-3 should raise exception when continuous attention required but unavailable."""
    with pytest.raises(AttentionInvariantViolation) as exc_info:
        validate_attention(
            requires_continuous_attention=True,
            attention_available=False,
            harm_scenario="financial transaction"
        )
    assert exc_info.value.invariant_id == "I-3"
    assert exc_info.value.harm_scenario == "financial transaction"


# ============================================================================
# I-4: TRUTH INVARIANT TESTS
# ============================================================================


def test_i4_truth_passes_when_all_satisfied():
    """I-4 should pass when claiming ALLOWED and all invariants satisfied."""
    validate_truth(
        satisfied_invariants={"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"},
        all_invariants={"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"},
        claiming_allowed=True
    )
    # No exception = pass


def test_i4_truth_passes_when_not_claiming_allowed():
    """I-4 should pass when not claiming ALLOWED, even if invariants unsatisfied."""
    validate_truth(
        satisfied_invariants={"I-1"},
        all_invariants={"I-1", "I-2", "I-3"},
        claiming_allowed=False
    )
    # No exception = pass


def test_i4_truth_fails_when_claiming_allowed_with_unsatisfied():
    """I-4 should raise exception when claiming ALLOWED with unsatisfied invariants."""
    with pytest.raises(TruthInvariantViolation) as exc_info:
        validate_truth(
            satisfied_invariants={"I-1", "I-2"},
            all_invariants={"I-1", "I-2", "I-3", "I-7"},
            claiming_allowed=True
        )
    assert exc_info.value.invariant_id == "I-4"
    assert "I-3" in exc_info.value.unsatisfied_invariants
    assert "I-7" in exc_info.value.unsatisfied_invariants


# ============================================================================
# I-5: LOGGING INVARIANT TESTS
# ============================================================================


def test_i5_logging_passes_when_logged():
    """I-5 should pass when event is logged."""
    validate_logging(
        event_logged=True,
        event_type="invariant_violation",
        suppression_detected=False
    )
    # No exception = pass


def test_i5_logging_fails_when_not_logged():
    """I-5 should raise exception when event is not logged."""
    with pytest.raises(LoggingInvariantViolation) as exc_info:
        validate_logging(
            event_logged=False,
            event_type="critical_event",
            suppression_detected=False
        )
    assert exc_info.value.invariant_id == "I-5"
    assert exc_info.value.suppression_attempt == "critical_event"


def test_i5_logging_fails_when_suppression_detected():
    """I-5 should raise exception when log suppression is detected."""
    with pytest.raises(LoggingInvariantViolation) as exc_info:
        validate_logging(
            event_logged=True,
            event_type="violation",
            suppression_detected=True
        )
    assert "suppression detected" in str(exc_info.value).lower()


# ============================================================================
# I-6: SILENCE INVARIANT TESTS
# ============================================================================


def test_i6_silence_passes_when_variable_resolved():
    """I-6 should pass when variable is resolved (no guessing needed)."""
    var = Variable(name="param", resolved=True, material=True, value=42)
    validate_silence(var, attempting_guess=False)
    # No exception = pass


def test_i6_silence_passes_when_not_guessing_unresolved():
    """I-6 should pass when variable is unresolved but not attempting to guess."""
    var = Variable(name="param", resolved=False, material=True)
    validate_silence(var, attempting_guess=False)
    # No exception = pass


def test_i6_silence_fails_when_guessing():
    """I-6 should raise exception when attempting to guess unresolved variable."""
    var = Variable(name="critical_param", resolved=False, material=True)
    with pytest.raises(SilenceInvariantViolation) as exc_info:
        validate_silence(var, attempting_guess=True)
    assert exc_info.value.invariant_id == "I-6"
    assert exc_info.value.variable_name == "critical_param"
    assert "guessing forbidden" in str(exc_info.value).lower()


# ============================================================================
# I-7: COMPLEXITY INVARIANT TESTS
# ============================================================================


def test_i7_complexity_passes_when_w_equals_0():
    """I-7 should pass when w=0 (no unresolved material variables)."""
    variables = [
        Variable("a", resolved=True, material=True, value=1),
        Variable("b", resolved=True, material=False, value=2),
    ]
    w = validate_complexity(variables, max_width=3)
    assert w == 0


def test_i7_complexity_passes_when_w_equals_3():
    """I-7 should pass when w=3 (at the limit)."""
    variables = [
        Variable("a", resolved=False, material=True),
        Variable("b", resolved=False, material=True),
        Variable("c", resolved=False, material=True),
    ]
    w = validate_complexity(variables, max_width=3)
    assert w == 3


def test_i7_complexity_ignores_non_material_variables():
    """I-7 should only count material variables in width calculation."""
    variables = [
        Variable("material1", resolved=False, material=True),
        Variable("non_material1", resolved=False, material=False),
        Variable("non_material2", resolved=False, material=False),
    ]
    w = validate_complexity(variables, max_width=3)
    assert w == 1


def test_i7_complexity_ignores_resolved_variables():
    """I-7 should only count unresolved variables in width calculation."""
    variables = [
        Variable("unresolved1", resolved=False, material=True),
        Variable("resolved1", resolved=True, material=True, value=10),
        Variable("resolved2", resolved=True, material=True, value=20),
    ]
    w = validate_complexity(variables, max_width=3)
    assert w == 1


def test_i7_complexity_fails_when_w_equals_4():
    """I-7 should raise exception when w=4 (exceeds limit of 3)."""
    variables = [
        Variable("a", resolved=False, material=True),
        Variable("b", resolved=False, material=True),
        Variable("c", resolved=False, material=True),
        Variable("d", resolved=False, material=True),
    ]
    with pytest.raises(ComplexityInvariantViolation) as exc_info:
        validate_complexity(variables, max_width=3)
    assert exc_info.value.invariant_id == "I-7"
    assert exc_info.value.measured_w == 4
    assert len(exc_info.value.unresolved_variables) == 4
    assert "a" in exc_info.value.unresolved_variables


def test_i7_complexity_fails_when_w_much_greater_than_limit():
    """I-7 should raise exception when w >> 3."""
    variables = [Variable(f"var{i}", resolved=False, material=True) for i in range(10)]
    with pytest.raises(ComplexityInvariantViolation) as exc_info:
        validate_complexity(variables, max_width=3)
    assert exc_info.value.measured_w == 10


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================


def test_get_all_invariant_ids():
    """Test that all seven invariant IDs are returned."""
    ids = get_all_invariant_ids()
    assert ids == {"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"}


def test_is_invariant_satisfied_i1():
    """Test is_invariant_satisfied for I-1."""
    assert is_invariant_satisfied(
        "I-1",
        required_definitions={"a": 1},
        required_thresholds={"b": 2},
        required_constraints=["c"]
    )
    assert not is_invariant_satisfied(
        "I-1",
        required_definitions={"a": None},
        required_thresholds={},
        required_constraints=[]
    )


def test_is_invariant_satisfied_i7():
    """Test is_invariant_satisfied for I-7."""
    variables = [Variable("a", resolved=True, material=True, value=1)]
    assert is_invariant_satisfied("I-7", variables=variables, max_width=3)

    variables = [Variable(f"v{i}", resolved=False, material=True) for i in range(5)]
    assert not is_invariant_satisfied("I-7", variables=variables, max_width=3)


# ============================================================================
# VARIABLE DATA STRUCTURE TESTS
# ============================================================================


def test_variable_resolved_must_have_value():
    """Test that resolved Variable must have a value."""
    with pytest.raises(ValueError, match="marked as resolved but has no value"):
        Variable(name="bad", resolved=True, material=True, value=None)


def test_variable_unresolved_can_have_no_value():
    """Test that unresolved Variable can have no value."""
    var = Variable(name="ok", resolved=False, material=True, value=None)
    assert var.name == "ok"
    assert not var.resolved


def test_authority_token_creation():
    """Test AuthorityToken creation."""
    token = AuthorityToken(
        source="admin",
        verifiable=True,
        scope="full_access",
        timestamp="2024-01-01T00:00:00Z"
    )
    assert token.source == "admin"
    assert token.verifiable
    assert token.scope == "full_access"
    assert token.timestamp == "2024-01-01T00:00:00Z"
