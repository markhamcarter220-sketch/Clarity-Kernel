"""
Tests for AIL (Adaptive Interaction Layer) Recursive Ambiguity Handling

These tests verify that the AIL wrapper correctly manages clarification
budgets and terminal ambiguity without modifying SSL behavior.
"""

import pytest
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    AILSession,
    AILWrapper,
    AILResponseType,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def kernel():
    """Creates a Clarity Kernel instance."""
    return ClarityKernel()


@pytest.fixture
def ail_session():
    """Creates an AIL session with default budget."""
    return AILSession(max_clarifications=2)


@pytest.fixture
def ail_wrapper(kernel, ail_session):
    """Creates an AIL wrapper."""
    return AILWrapper(kernel, ail_session)


def create_ambiguous_request(operation_id: str = "ambiguous_op"):
    """
    Creates a permission request with ambiguous definitions (triggers I-1).

    Args:
        operation_id: Unique operation identifier

    Returns:
        PermissionRequest with ambiguous elements
    """
    return PermissionRequest(
        operation_id=operation_id,
        variables=[
            Variable("param1", resolved=True, material=True, value=1),
        ],
        required_definitions={
            "mode": None,  # AMBIGUOUS - violates I-1
        },
        required_thresholds={"max": 10},
        required_constraints=["valid"],
        authority=AuthorityToken("test", True, "test_scope"),
        required_scope="test_scope",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario=""
    )


def create_resolved_request(operation_id: str = "resolved_op"):
    """
    Creates a permission request with all definitions resolved.

    Args:
        operation_id: Unique operation identifier

    Returns:
        PermissionRequest with no ambiguity
    """
    return PermissionRequest(
        operation_id=operation_id,
        variables=[
            Variable("param1", resolved=True, material=True, value=1),
        ],
        required_definitions={
            "mode": "safe",  # RESOLVED
        },
        required_thresholds={"max": 10},
        required_constraints=["valid"],
        authority=AuthorityToken("test", True, "test_scope"),
        required_scope="test_scope",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario=""
    )


def create_no_authority_request(operation_id: str = "no_auth_op"):
    """
    Creates a permission request without authority (triggers I-2, not I-1).

    Args:
        operation_id: Unique operation identifier

    Returns:
        PermissionRequest with missing authority
    """
    return PermissionRequest(
        operation_id=operation_id,
        variables=[
            Variable("param1", resolved=True, material=True, value=1),
        ],
        required_definitions={"mode": "safe"},
        required_thresholds={"max": 10},
        required_constraints=["valid"],
        authority=None,  # NO AUTHORITY - violates I-2
        required_scope="test_scope",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario=""
    )


# ============================================================================
# TEST A: Two Clarifications → TAD → Silence
# ============================================================================


def test_recursive_ambiguity_budget_and_tad(ail_wrapper):
    """
    Test that AIL provides 2 clarifications, then TAD, then silence.

    Expected flow:
    1. First ambiguous input → CLARIFY
    2. Second ambiguous input (same) → CLARIFY
    3. Third ambiguous input (same) → TAD
    4. Fourth ambiguous input (same) → SILENCE
    """
    request = create_ambiguous_request()

    # First attempt - should clarify
    resp1 = ail_wrapper.step(request)
    assert resp1.response_type == AILResponseType.CLARIFY
    assert "missing definitions" in resp1.message.lower()
    assert resp1.context["attempts"] == 1

    # Second attempt - should clarify again
    resp2 = ail_wrapper.step(request)
    assert resp2.response_type == AILResponseType.CLARIFY
    assert resp2.context["attempts"] == 2

    # Third attempt - budget exhausted, TAD
    resp3 = ail_wrapper.step(request)
    assert resp3.response_type == AILResponseType.TAD
    assert "ambiguous in a way that does not admit" in resp3.message
    assert resp3.context["terminal"] is True

    # Fourth attempt - silence after TAD
    resp4 = ail_wrapper.step(request)
    assert resp4.response_type == AILResponseType.SILENCE
    assert resp4.message == ""


def test_tad_message_is_canonical(ail_wrapper):
    """Test that TAD message matches specification exactly."""
    request = create_ambiguous_request()

    # Exhaust budget
    ail_wrapper.step(request)
    ail_wrapper.step(request)
    resp_tad = ail_wrapper.step(request)

    expected = (
        "The question remains ambiguous in a way that does not admit a determinate answer "
        "without introducing assumptions. Under the Clarity Kernel, further resolution is not "
        "possible without violating inference constraints."
    )
    assert resp_tad.message == expected


# ============================================================================
# TEST B: New Input Resets Session
# ============================================================================


def test_new_input_resets_ambiguity_tracker(kernel):
    """
    Test that providing new (resolved) input resets the AIL session.

    Expected flow:
    1. Ambiguous input → CLARIFY
    2. Different input (resolved) → PASSTHROUGH (allowed)
    3. Session should be reset
    """
    session = AILSession(max_clarifications=2)
    wrapper = AILWrapper(kernel, session)

    # First: ambiguous request
    ambiguous_req = create_ambiguous_request("op1")
    resp1 = wrapper.step(ambiguous_req)
    assert resp1.response_type == AILResponseType.CLARIFY
    assert session.clarification_attempts == 1

    # Second: resolved request (different fingerprint)
    resolved_req = create_resolved_request("op2")
    resp2 = wrapper.step(resolved_req)
    assert resp2.response_type == AILResponseType.PASSTHROUGH
    assert resp2.ssl_response.granted is True

    # Session should be reset
    assert session.clarification_attempts == 0
    assert session.terminal_declared is False
    assert session.last_ambiguity_fingerprint is None


def test_same_ambiguity_increments_attempts(ail_wrapper):
    """Test that repeating the same ambiguous input increments attempts."""
    request = create_ambiguous_request()

    resp1 = ail_wrapper.step(request)
    assert resp1.context["attempts"] == 1

    resp2 = ail_wrapper.step(request)
    assert resp2.context["attempts"] == 2


def test_different_ambiguous_input_does_not_reset(kernel):
    """
    Test that different ambiguous inputs (before resolution) continue counting.

    This ensures we don't reset on "different but still ambiguous" inputs.
    """
    session = AILSession(max_clarifications=2)
    wrapper = AILWrapper(kernel, session)

    # First ambiguous request
    req1 = create_ambiguous_request("op1")
    resp1 = wrapper.step(req1)
    assert resp1.response_type == AILResponseType.CLARIFY
    assert session.clarification_attempts == 1

    # Different ambiguous request (still violates I-1)
    req2 = create_ambiguous_request("op2")
    resp2 = wrapper.step(req2)
    assert resp2.response_type == AILResponseType.CLARIFY
    assert session.clarification_attempts == 2

    # Third attempt should TAD
    req3 = create_ambiguous_request("op3")
    resp3 = wrapper.step(req3)
    assert resp3.response_type == AILResponseType.TAD


# ============================================================================
# TEST C: Non-Ambiguity STOP Passes Through
# ============================================================================


def test_non_ambiguity_stop_passes_through(ail_wrapper):
    """
    Test that non-ambiguity STOP (e.g., I-2 violation) passes through unchanged.

    AIL should NOT attempt clarification for non-I-1 invariant violations.
    """
    # Request with missing authority (I-2 violation, not I-1)
    request = create_no_authority_request()

    resp = ail_wrapper.step(request)

    # Should passthrough, not attempt clarification
    assert resp.response_type == AILResponseType.PASSTHROUGH
    assert "authority" in resp.message.lower()
    assert ail_wrapper.session.clarification_attempts == 0


def test_non_ambiguity_stop_does_not_count_toward_budget(kernel):
    """
    Test that I-2 violations don't consume clarification budget.
    """
    session = AILSession(max_clarifications=2)
    wrapper = AILWrapper(kernel, session)

    # Try I-2 violation multiple times
    req = create_no_authority_request()

    resp1 = wrapper.step(req)
    assert resp1.response_type == AILResponseType.PASSTHROUGH
    assert session.clarification_attempts == 0

    resp2 = wrapper.step(req)
    assert resp2.response_type == AILResponseType.PASSTHROUGH
    assert session.clarification_attempts == 0

    # Should still have full budget for actual ambiguity
    ambiguous_req = create_ambiguous_request()
    resp3 = wrapper.step(ambiguous_req)
    assert resp3.response_type == AILResponseType.CLARIFY
    assert session.clarification_attempts == 1


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


def test_session_reset_clears_all_state(ail_session):
    """Test that session reset clears all tracking state."""
    ail_session.clarification_attempts = 2
    ail_session.terminal_declared = True
    ail_session.last_ambiguity_fingerprint = "abc123"

    ail_session.reset()

    assert ail_session.clarification_attempts == 0
    assert ail_session.terminal_declared is False
    assert ail_session.last_ambiguity_fingerprint is None


def test_custom_clarification_budget(kernel):
    """Test that custom clarification budgets work correctly."""
    session = AILSession(max_clarifications=1)  # Only 1 clarification allowed
    wrapper = AILWrapper(kernel, session)

    request = create_ambiguous_request()

    # First attempt - clarify
    resp1 = wrapper.step(request)
    assert resp1.response_type == AILResponseType.CLARIFY

    # Second attempt - TAD (budget was 1)
    resp2 = wrapper.step(request)
    assert resp2.response_type == AILResponseType.TAD


def test_zero_budget_goes_straight_to_tad(kernel):
    """Test that zero clarification budget goes directly to TAD."""
    session = AILSession(max_clarifications=0)
    wrapper = AILWrapper(kernel, session)

    request = create_ambiguous_request()

    # First attempt should be TAD
    resp = wrapper.step(request)
    assert resp.response_type == AILResponseType.TAD


def test_ail_preserves_ssl_response_on_passthrough(ail_wrapper):
    """Test that AIL preserves full SSL response on passthrough."""
    request = create_resolved_request()

    resp = ail_wrapper.step(request)

    assert resp.response_type == AILResponseType.PASSTHROUGH
    assert resp.ssl_response is not None
    assert resp.ssl_response.granted is True
    assert resp.ssl_response.measured_w == 0


# ============================================================================
# FINGERPRINT TESTS
# ============================================================================


def test_fingerprint_detects_identical_requests(kernel):
    """Test that identical requests produce the same fingerprint."""
    session = AILSession(max_clarifications=2)
    wrapper = AILWrapper(kernel, session)

    req1 = create_ambiguous_request("same_op")
    req2 = create_ambiguous_request("same_op")

    # Both should produce same fingerprint
    fp1 = wrapper._compute_fingerprint(req1)
    fp2 = wrapper._compute_fingerprint(req2)

    assert fp1 == fp2


def test_fingerprint_detects_different_requests(kernel):
    """Test that different requests produce different fingerprints."""
    session = AILSession(max_clarifications=2)
    wrapper = AILWrapper(kernel, session)

    req1 = create_ambiguous_request("op1")
    req2 = create_ambiguous_request("op2")

    fp1 = wrapper._compute_fingerprint(req1)
    fp2 = wrapper._compute_fingerprint(req2)

    assert fp1 != fp2
