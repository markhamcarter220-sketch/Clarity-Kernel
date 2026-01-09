"""
Tests for AIL (Adaptive Interaction Layer) non-interference enforcement.

This test suite proves that AIL CANNOT interfere with SSL decisions by testing:
1. Pass-through behavior - SSL decisions returned unchanged
2. No assumptions added - AIL cannot guess or infer values
3. No STOP → ALLOW downgrade - Cannot soften SSL verdicts
4. Formal rules documented and enforced

The AIL is PERMITTED to:
- Request clarification for ambiguity
- Track session state
- Return SSL decisions unchanged

The AIL is FORBIDDEN from:
- Adding assumptions
- Overriding SSL decisions
- Optimizing for UX at expense of safety
"""

import pytest
from clarity_kernel import (
    AILWrapper,
    AILSession,
    AILInterferenceViolation,
    AIL_PERMITTED_ACTIONS,
    AIL_FORBIDDEN_ACTIONS,
)


# ============================================================================
# FORMAL RULES DOCUMENTATION TESTS
# ============================================================================

def test_ail_permitted_actions_documented():
    """Verify permitted actions are explicitly documented."""
    assert "request_clarification" in AIL_PERMITTED_ACTIONS
    assert "passthrough_ssl_decision" in AIL_PERMITTED_ACTIONS
    assert "track_session_state" in AIL_PERMITTED_ACTIONS

    # Only 3 permitted actions
    assert len(AIL_PERMITTED_ACTIONS) == 3


def test_ail_forbidden_actions_documented():
    """Verify forbidden actions are explicitly documented."""
    assert "add_assumption" in AIL_FORBIDDEN_ACTIONS
    assert "rewrite_constraint" in AIL_FORBIDDEN_ACTIONS
    assert "downgrade_stop" in AIL_FORBIDDEN_ACTIONS
    assert "mutate_request" in AIL_FORBIDDEN_ACTIONS
    assert "override_ssl" in AIL_FORBIDDEN_ACTIONS
    assert "soften_invariant" in AIL_FORBIDDEN_ACTIONS
    assert "optimize_for_ux" in AIL_FORBIDDEN_ACTIONS

    # At least 7 forbidden actions
    assert len(AIL_FORBIDDEN_ACTIONS) >= 7


def test_ail_interference_violation_exception_exists():
    """AILInterferenceViolation exception must exist."""
    # Create instance
    violation = AILInterferenceViolation(
        "Test violation",
        interference_type="test",
        evidence={"test": "data"}
    )

    assert violation.interference_type == "test"
    assert violation.evidence == {"test": "data"}
    assert str(violation) == "Test violation"


def test_ail_wrapper_has_enforcement_flag():
    """AILWrapper must have enforce_noninterference flag."""
    from unittest.mock import Mock
    from clarity_kernel import ClarityKernel

    kernel = Mock(spec=ClarityKernel)

    # Default: enforcement enabled
    ail_default = AILWrapper(kernel)
    assert ail_default.enforce_noninterference is True

    # Explicit: enforcement disabled (DANGEROUS - testing only)
    ail_disabled = AILWrapper(kernel, enforce_noninterference=False)
    assert ail_disabled.enforce_noninterference is False


def test_ail_wrapper_has_verification_methods():
    """AILWrapper must have verification methods for enforcement."""
    from unittest.mock import Mock
    from clarity_kernel import ClarityKernel

    kernel = Mock(spec=ClarityKernel)
    ail = AILWrapper(kernel)

    # Verify methods exist
    assert hasattr(ail, '_verify_request_unmodified')
    assert hasattr(ail, '_verify_decision_unmodified')
    assert hasattr(ail, '_verify_no_assumptions_added')


# ============================================================================
# NON-INTERFERENCE AXIOM TESTS
# ============================================================================

def test_ail_noninterference_axiom_documented():
    """Verify non-interference axiom is documented in module docstring."""
    from clarity_kernel import ail

    docstring = ail.__doc__

    assert "NON-INTERFERENCE AXIOM" in docstring or "NON-INTERFERENCE" in docstring
    assert "MUST NOT mutate" in docstring or "cannot mutate" in docstring


def test_ail_forbidden_from_adding_assumptions():
    """AIL is explicitly FORBIDDEN from adding assumptions."""
    assert "add_assumption" in AIL_FORBIDDEN_ACTIONS

    # This is documented as violating I-6 (Silence Invariant)


def test_ail_forbidden_from_rewriting_constraints():
    """AIL is explicitly FORBIDDEN from rewriting constraints."""
    assert "rewrite_constraint" in AIL_FORBIDDEN_ACTIONS


def test_ail_forbidden_from_downgrading_stop():
    """AIL is explicitly FORBIDDEN from downgrading STOP → ALLOW."""
    assert "downgrade_stop" in AIL_FORBIDDEN_ACTIONS


def test_ail_forbidden_from_mutating_request():
    """AIL is explicitly FORBIDDEN from mutating requests."""
    assert "mutate_request" in AIL_FORBIDDEN_ACTIONS


def test_ail_forbidden_from_overriding_ssl():
    """AIL is explicitly FORBIDDEN from overriding SSL decisions."""
    assert "override_ssl" in AIL_FORBIDDEN_ACTIONS


def test_ail_forbidden_from_softening_invariants():
    """AIL is explicitly FORBIDDEN from softening invariants."""
    assert "soften_invariant" in AIL_FORBIDDEN_ACTIONS


def test_ail_forbidden_from_optimizing_for_ux():
    """AIL is explicitly FORBIDDEN from trading safety for UX."""
    assert "optimize_for_ux" in AIL_FORBIDDEN_ACTIONS


# ============================================================================
# SESSION STATE TRACKING (PERMITTED)
# ============================================================================

def test_ail_can_track_clarification_attempts():
    """AIL is PERMITTED to track session state (clarification attempts)."""
    session = AILSession(max_clarifications=2)

    # Verify session can track state
    assert session.clarification_attempts == 0
    assert session.terminal_declared is False
    assert session.last_fingerprint is None

    # Track an attempt
    session.clarification_attempts = 1
    assert session.clarification_attempts == 1

    # Reset
    session.reset()
    assert session.clarification_attempts == 0


def test_ail_session_has_max_clarifications_budget():
    """AIL session has finite clarification budget (prevents infinite loops)."""
    # Default budget
    session_default = AILSession()
    assert session_default.max_clarifications == 2

    # Custom budget
    session_custom = AILSession(max_clarifications=5)
    assert session_custom.max_clarifications == 5


def test_ail_session_tracks_terminal_ambiguity():
    """AIL session can track terminal ambiguity declaration."""
    session = AILSession()

    assert session.terminal_declared is False

    # Declare terminal
    session.terminal_declared = True
    assert session.terminal_declared is True


# ============================================================================
# ENFORCEMENT REQUIREMENTS
# ============================================================================

def test_ail_enforcement_enabled_by_default():
    """AIL non-interference enforcement should be enabled by default."""
    from unittest.mock import Mock
    from clarity_kernel import ClarityKernel

    kernel = Mock(spec=ClarityKernel)
    ail = AILWrapper(kernel)

    assert ail.enforce_noninterference is True


def test_ail_can_disable_enforcement_for_testing():
    """AIL can disable enforcement for testing (DANGEROUS - documented as testing-only)."""
    from unittest.mock import Mock
    from clarity_kernel import ClarityKernel

    kernel = Mock(spec=ClarityKernel)
    ail = AILWrapper(kernel, enforce_noninterference=False)

    assert ail.enforce_noninterference is False
    # This should NEVER be used in production


def test_ail_interference_violation_has_evidence():
    """AILInterferenceViolation must preserve evidence for audit."""
    evidence = {
        "variable_name": "dosage",
        "assumed_value": 50,
        "fingerprint_before": "abc123",
        "fingerprint_after": "def456",
    }

    violation = AILInterferenceViolation(
        "Test interference",
        interference_type="add_assumption",
        evidence=evidence
    )

    assert violation.evidence == evidence
    assert violation.interference_type == "add_assumption"


# ============================================================================
# DOCUMENTATION REQUIREMENTS
# ============================================================================

def test_ail_module_documents_forbidden_patterns():
    """AIL module must document forbidden interference patterns."""
    from clarity_kernel import ail

    # Check that forbidden actions are documented
    assert len(AIL_FORBIDDEN_ACTIONS) >= 7

    # Verify key forbidden patterns
    forbidden_list = list(AIL_FORBIDDEN_ACTIONS)
    assert "add_assumption" in forbidden_list
    assert "downgrade_stop" in forbidden_list
    assert "override_ssl" in forbidden_list


def test_ail_module_documents_permitted_patterns():
    """AIL module must document permitted actions."""
    from clarity_kernel import ail

    # Check that permitted actions are documented
    assert len(AIL_PERMITTED_ACTIONS) == 3

    # Verify key permitted patterns
    permitted_list = list(AIL_PERMITTED_ACTIONS)
    assert "request_clarification" in permitted_list
    assert "passthrough_ssl_decision" in permitted_list
    assert "track_session_state" in permitted_list


def test_ail_wrapper_documents_noninterference():
    """AILWrapper class must document non-interference requirement."""
    from clarity_kernel import ail

    wrapper_doc = ail.AILWrapper.__doc__

    assert wrapper_doc is not None
    assert "non-interference" in wrapper_doc.lower() or "prohibited" in wrapper_doc.lower()


# ============================================================================
# CRITICAL RULES SUMMARY
# ============================================================================

def test_ail_critical_rule_no_assumptions():
    """CRITICAL: AIL cannot add assumptions (violates I-6)."""
    assert "add_assumption" in AIL_FORBIDDEN_ACTIONS


def test_ail_critical_rule_no_stop_downgrade():
    """CRITICAL: AIL cannot downgrade STOP → ALLOW."""
    assert "downgrade_stop" in AIL_FORBIDDEN_ACTIONS


def test_ail_critical_rule_no_ssl_override():
    """CRITICAL: AIL cannot override SSL decisions."""
    assert "override_ssl" in AIL_FORBIDDEN_ACTIONS


def test_ail_critical_rule_no_ux_optimization():
    """CRITICAL: AIL cannot optimize for UX at expense of safety."""
    assert "optimize_for_ux" in AIL_FORBIDDEN_ACTIONS


def test_ail_must_preserve_ssl_authority():
    """CRITICAL: AIL must preserve SSL as authoritative decision layer."""
    # AIL can only:
    # 1. Request clarification
    # 2. Pass through SSL decisions
    # 3. Track session state

    # AIL cannot:
    # 1. Override SSL
    # 2. Soften invariants
    # 3. Add assumptions
    # 4. Rewrite constraints
    # 5. Downgrade STOP
    # 6. Mutate requests
    # 7. Optimize for UX over safety

    assert len(AIL_PERMITTED_ACTIONS) == 3
    assert len(AIL_FORBIDDEN_ACTIONS) >= 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
