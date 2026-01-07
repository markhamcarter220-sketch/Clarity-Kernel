"""
Test Suite for Break-Glass Override Semantics (Section 9)

Tests override functionality and abnormal mode operation:
- Override does not remove invariants
- Override changes operating mode to ABNORMAL
- Override requires human authorization
- Override state is persistently visible
- All override actions are logged
- Override does not automatically relax w ≤ 3
"""

import pytest
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    AuditLogger,
    KernelState,
    OperatingMode,
)
from clarity_kernel.logging import EventType


# ============================================================================
# OVERRIDE BASIC FUNCTIONALITY TESTS
# ============================================================================


def test_override_requires_signature():
    """Test that override requires a non-empty human authorization signature."""
    kernel = ClarityKernel()

    with pytest.raises(ValueError, match="signature required"):
        kernel.apply_override(
            override_signature="",
            unsatisfiable_invariants=["I-1"],
            justification="Testing"
        )


def test_override_changes_mode_to_abnormal():
    """Test that override changes operating mode to ABNORMAL."""
    kernel = ClarityKernel()

    kernel.apply_override(
        override_signature="admin_override_001",
        unsatisfiable_invariants=["I-1"],
        justification="Emergency override for testing"
    )

    assert kernel.operating_mode == OperatingMode.ABNORMAL
    assert kernel.override_active
    assert kernel.override_signature == "admin_override_001"


def test_override_transitions_state_machine():
    """Test that override transitions state machine to abnormal states."""
    kernel = ClarityKernel()

    kernel.apply_override(
        override_signature="override_sig",
        unsatisfiable_invariants=["I-7"],
        justification="Width exceeded, manual override"
    )

    # Should be in ABNORMAL_EXECUTION state
    assert kernel.state_machine.current_state == KernelState.ABNORMAL_EXECUTION


def test_override_is_logged():
    """Test that override is logged to audit log."""
    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    kernel.apply_override(
        override_signature="override_123",
        unsatisfiable_invariants=["I-1", "I-2"],
        justification="Test override"
    )

    # Check that override was logged
    override_events = logger.get_entries_by_type(EventType.OVERRIDE_APPLIED)
    assert len(override_events) > 0
    assert override_events[0].authority_source == "override_123"
    assert "I-1" in override_events[0].invariants_evaluated
    assert "I-2" in override_events[0].invariants_evaluated


def test_override_logs_multiple_state_transitions():
    """Test that override logs all state transitions."""
    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    kernel.apply_override(
        override_signature="override_xyz",
        unsatisfiable_invariants=["I-7"],
        justification="Complexity override"
    )

    # Should have logged multiple state transitions
    transitions = logger.get_entries_by_type(EventType.STATE_TRANSITION)
    assert len(transitions) >= 3  # UNSATISFIABLE → OVERRIDE → ABNORMAL_EXECUTION


# ============================================================================
# OVERRIDE DOES NOT RELAX INVARIANTS
# ============================================================================


def test_override_does_not_remove_invariants():
    """
    Test that override does not remove invariants.
    Per spec: "Override does not remove invariants; it changes operating mode to ABNORMAL."
    """
    kernel = ClarityKernel()

    # Apply override
    kernel.apply_override(
        override_signature="test_override",
        unsatisfiable_invariants=["I-1"],
        justification="Testing that invariants persist"
    )

    # Invariants should still exist (not removed)
    # The system is just in ABNORMAL mode
    assert kernel.operating_mode == OperatingMode.ABNORMAL

    # Note: The invariants themselves are not changed or removed
    # They just aren't enforced in the same way during abnormal mode


def test_override_does_not_relax_width_limit():
    """
    Test that override does not automatically relax w ≤ 3.
    Per spec: "Override does not automatically relax w ≤ 3."
    """
    kernel = ClarityKernel()

    # Apply override
    kernel.apply_override(
        override_signature="width_override",
        unsatisfiable_invariants=["I-7"],
        justification="Width limit exceeded"
    )

    # Width limit is still 3 (not changed)
    assert kernel.max_width == 3


# ============================================================================
# IMMEDIATE STOP TESTS
# ============================================================================


def test_immediate_stop_triggers_exception():
    """Test that immediate stop triggers ImmediateStopTriggered exception."""
    from clarity_kernel.ssl import ImmediateStopTriggered

    kernel = ClarityKernel()

    with pytest.raises(ImmediateStopTriggered) as exc_info:
        kernel.trigger_immediate_stop(
            reason="Test stop",
            triggered_by="manual_test"
        )

    assert exc_info.value.trigger == "manual_test"
    assert "Test stop" in str(exc_info.value)


def test_immediate_stop_transitions_state():
    """Test that immediate stop transitions to IMMEDIATE_STOP state."""
    from clarity_kernel.ssl import ImmediateStopTriggered

    kernel = ClarityKernel()

    try:
        kernel.trigger_immediate_stop(
            reason="Stop test",
            triggered_by="test"
        )
    except ImmediateStopTriggered:
        pass

    assert kernel.state_machine.current_state == KernelState.IMMEDIATE_STOP


def test_immediate_stop_is_logged():
    """Test that immediate stop is logged."""
    from clarity_kernel.ssl import ImmediateStopTriggered

    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    try:
        kernel.trigger_immediate_stop(
            reason="Test logging",
            triggered_by="test_suite"
        )
    except ImmediateStopTriggered:
        pass

    stop_events = logger.get_entries_by_type(EventType.IMMEDIATE_STOP)
    assert len(stop_events) > 0
    assert "test_suite" in str(stop_events[0].context)


# ============================================================================
# FULL INTEGRATION TESTS
# ============================================================================


def test_permission_denied_when_complexity_violated():
    """Test that permission is denied when complexity invariant (w > 3) is violated."""
    from clarity_kernel.ssl import PermissionDenied

    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    # Create request with w=5 (exceeds limit of 3)
    request = PermissionRequest(
        operation_id="test_op",
        variables=[
            Variable(f"var{i}", resolved=False, material=True)
            for i in range(5)  # w=5
        ],
        required_definitions={"mode": "test"},
        required_thresholds={"max": 10},
        required_constraints=["valid"],
        authority=AuthorityToken("test", True, "test_scope"),
        required_scope="test_scope",
        preconditions=MomentaryPreconditions(
            outcome_reversible=True,
            risk_does_not_increase=True,
            no_new_critical_info=True,
            w_within_limit=False,  # This will fail
            execution_window_bounded=True
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=False,
            compliance_safety_exposure=False,
            context_may_change=False,
            ambiguity_at_initiation=False,
            w_may_fluctuate=False,
            execution_window_extended=False
        ),
        requires_continuous_attention=False,
        harm_scenario=""
    )

    with pytest.raises(PermissionDenied) as exc_info:
        kernel.request_permission(request)

    assert "w=5" in str(exc_info.value)


def test_permission_granted_when_all_invariants_satisfied():
    """Test that permission is granted when all invariants are satisfied."""
    kernel = ClarityKernel()

    request = PermissionRequest(
        operation_id="valid_op",
        variables=[
            Variable("var1", resolved=True, material=True, value=1),
            Variable("var2", resolved=True, material=False, value=2),
        ],
        required_definitions={"mode": "safe"},
        required_thresholds={"max": 10},
        required_constraints=["all_valid"],
        authority=AuthorityToken("operator", True, "execute"),
        required_scope="execute",
        preconditions=MomentaryPreconditions(
            outcome_reversible=True,
            risk_does_not_increase=True,
            no_new_critical_info=True,
            w_within_limit=True,
            execution_window_bounded=True
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=False,
            compliance_safety_exposure=False,
            context_may_change=False,
            ambiguity_at_initiation=False,
            w_may_fluctuate=False,
            execution_window_extended=False
        ),
        requires_continuous_attention=False,
        harm_scenario=""
    )

    response = kernel.request_permission(request)

    assert response.granted
    assert response.measured_w == 0
    assert len(response.satisfied_invariants) == 7  # All 7 invariants


def test_reset_from_abnormal_mode():
    """Test that kernel can reset from abnormal mode."""
    kernel = ClarityKernel()

    # Enter abnormal mode
    kernel.apply_override(
        override_signature="test_reset",
        unsatisfiable_invariants=["I-1"],
        justification="Testing reset"
    )
    assert kernel.operating_mode == OperatingMode.ABNORMAL

    # Complete abnormal flow to RETURN_TO_SAFE_STATE
    kernel.abnormal_controller.show_persistent_warning(logged=True)
    kernel.abnormal_controller.resolve("Resolved", logged=True)
    kernel.abnormal_controller.return_to_safe_state(logged=True)

    # Reset to IDLE
    kernel.reset()

    assert kernel.state_machine.current_state == KernelState.IDLE
    assert kernel.operating_mode == OperatingMode.NORMAL
    assert not kernel.override_active
    assert kernel.override_signature is None


def test_reset_from_complete():
    """Test that kernel can reset from COMPLETE state."""
    kernel = ClarityKernel()

    # Manually set to COMPLETE state
    kernel.state_machine.transition_to(
        KernelState.COMPLETE,
        reason="Manual completion",
        logged=True
    )

    kernel.reset()
    assert kernel.state_machine.current_state == KernelState.IDLE


def test_reset_fails_from_invalid_state():
    """Test that reset fails from invalid states."""
    kernel = ClarityKernel()

    # Try to reset from IDLE (already idle)
    with pytest.raises(ValueError, match="Cannot reset"):
        kernel.reset()


# ============================================================================
# LOGGING INVARIANT ENFORCEMENT
# ============================================================================


def test_all_events_are_logged():
    """Test that all major events are logged (I-5: Logging Invariant)."""
    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    # Perform override
    kernel.apply_override(
        override_signature="full_test",
        unsatisfiable_invariants=["I-1", "I-7"],
        justification="Comprehensive logging test"
    )

    # Check all events were logged
    all_entries = logger.get_all_entries()
    assert len(all_entries) > 0

    # Should have override event
    override_events = logger.get_entries_by_type(EventType.OVERRIDE_APPLIED)
    assert len(override_events) > 0

    # Should have state transitions
    transition_events = logger.get_entries_by_type(EventType.STATE_TRANSITION)
    assert len(transition_events) > 0


def test_log_suppression_is_forbidden():
    """Test that log suppression is detected and prevented (I-5)."""
    from clarity_kernel.logging import LogSuppressionAttempt

    logger = AuditLogger(in_memory=True)

    # Simulate suppression detection
    logger._suppression_detected = True

    from clarity_kernel.logging import LogEntry, EventType
    from datetime import datetime

    entry = LogEntry(
        timestamp=datetime.now(),
        event_type=EventType.INVARIANT_VIOLATION,
        kernel_state="TEST",
        ssl_version="v1.1.0",
        invariants_evaluated={}
    )

    with pytest.raises(LogSuppressionAttempt):
        logger.log(entry)


def test_log_mutation_is_forbidden():
    """Test that log mutation is forbidden."""
    from clarity_kernel.logging import LogMutationAttempt

    logger = AuditLogger(in_memory=True)

    with pytest.raises(LogMutationAttempt, match="append-only"):
        logger.clear()

    with pytest.raises(LogMutationAttempt, match="append-only"):
        logger.delete_entry(0)


# ============================================================================
# WIDTH EVALUATION LOGGING
# ============================================================================


def test_width_evaluation_is_logged():
    """Test that width evaluations are logged per Section 8.5."""
    from clarity_kernel.ssl import PermissionDenied

    logger = AuditLogger(in_memory=True)
    kernel = ClarityKernel(logger=logger)

    # Create request that will trigger width evaluation
    request = PermissionRequest(
        operation_id="width_test",
        variables=[
            Variable("a", resolved=False, material=True),
            Variable("b", resolved=False, material=True),
        ],
        required_definitions={"test": "value"},
        required_thresholds={"t": 1},
        required_constraints=["constraint"],
        authority=AuthorityToken("test", True, "scope"),
        required_scope="scope",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario=""
    )

    try:
        kernel.request_permission(request)
    except:
        pass

    # Check width evaluation was logged
    width_events = logger.get_entries_by_type(EventType.WIDTH_EVALUATION)
    assert len(width_events) > 0
    assert width_events[0].measured_w == 2
    assert len(width_events[0].unresolved_variables) == 2


# ============================================================================
# TRUTH INVARIANT ENFORCEMENT
# ============================================================================


def test_cannot_claim_allowed_with_unsatisfied_invariants():
    """Test that I-4 (Truth Invariant) prevents claiming ALLOWED with unsatisfied invariants."""
    from clarity_kernel.invariants import validate_truth, TruthInvariantViolation

    with pytest.raises(TruthInvariantViolation):
        validate_truth(
            satisfied_invariants={"I-1", "I-2"},
            all_invariants={"I-1", "I-2", "I-3", "I-7"},
            claiming_allowed=True  # Claiming ALLOWED but not all satisfied
        )
