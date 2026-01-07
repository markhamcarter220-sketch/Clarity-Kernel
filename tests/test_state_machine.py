"""
Test Suite for Clarity Kernel State Machine

Tests all state transitions from Section 7:
1. Normal Mode
2. Continuous Authorization Mode
3. Abnormal/Override Mode (Break-Glass)

Critical requirement: No silent transitions are permitted.
"""

import pytest
from clarity_kernel.state_machine import (
    KernelState,
    OperatingMode,
    ClarityStateMachine,
    StateMachineContext,
    NormalModeController,
    ContinuousModeController,
    AbnormalModeController,
    StateTransition,
    InvalidStateTransition,
    SilentTransitionAttempt,
)


# ============================================================================
# STATE MACHINE CORE TESTS
# ============================================================================


def test_state_machine_starts_in_idle():
    """Test that state machine starts in IDLE state."""
    sm = ClarityStateMachine()
    assert sm.get_current_state() == KernelState.IDLE


def test_state_machine_can_start_in_custom_state():
    """Test that state machine can start in a specified state."""
    sm = ClarityStateMachine(initial_state=KernelState.PRECONDITIONS_VALID)
    assert sm.get_current_state() == KernelState.PRECONDITIONS_VALID


def test_can_transition_to_valid_state():
    """Test that can_transition_to returns True for valid transitions."""
    sm = ClarityStateMachine()
    assert sm.can_transition_to(KernelState.PRECONDITIONS_VALID)
    assert sm.can_transition_to(KernelState.INVARIANT_UNSATISFIABLE)


def test_cannot_transition_to_invalid_state():
    """Test that can_transition_to returns False for invalid transitions."""
    sm = ClarityStateMachine()
    assert not sm.can_transition_to(KernelState.EXECUTING)
    assert not sm.can_transition_to(KernelState.COMPLETE)


def test_transition_to_valid_state_succeeds():
    """Test that transition to valid state succeeds."""
    sm = ClarityStateMachine()
    transition = sm.transition_to(
        KernelState.PRECONDITIONS_VALID,
        reason="Testing transition",
        logged=True
    )
    assert sm.get_current_state() == KernelState.PRECONDITIONS_VALID
    assert transition.from_state == KernelState.IDLE
    assert transition.to_state == KernelState.PRECONDITIONS_VALID


def test_transition_to_invalid_state_fails():
    """Test that transition to invalid state raises exception."""
    sm = ClarityStateMachine()
    with pytest.raises(InvalidStateTransition) as exc_info:
        sm.transition_to(
            KernelState.EXECUTING,
            reason="Invalid transition",
            logged=True
        )
    assert exc_info.value.from_state == KernelState.IDLE
    assert exc_info.value.to_state == KernelState.EXECUTING


def test_silent_transition_forbidden():
    """Test that silent transitions (not logged) are forbidden."""
    sm = ClarityStateMachine()
    with pytest.raises(SilentTransitionAttempt) as exc_info:
        sm.transition_to(
            KernelState.PRECONDITIONS_VALID,
            reason="Silent transition attempt",
            logged=False  # FORBIDDEN
        )
    assert exc_info.value.from_state == KernelState.IDLE
    assert exc_info.value.to_state == KernelState.PRECONDITIONS_VALID


def test_empty_reason_forbidden():
    """Test that transitions require non-empty reason."""
    sm = ClarityStateMachine()
    with pytest.raises(ValueError, match="reason cannot be empty"):
        sm.transition_to(
            KernelState.PRECONDITIONS_VALID,
            reason="",
            logged=True
        )


def test_transition_history_maintained():
    """Test that transition history is maintained."""
    sm = ClarityStateMachine()
    sm.transition_to(KernelState.PRECONDITIONS_VALID, "Step 1", logged=True)
    sm.transition_to(KernelState.WIDTH_OK, "Step 2", logged=True)

    history = sm.get_transition_history()
    assert len(history) == 2
    assert history[0].to_state == KernelState.PRECONDITIONS_VALID
    assert history[1].to_state == KernelState.WIDTH_OK


def test_transition_context_stored():
    """Test that transition context is stored."""
    sm = ClarityStateMachine()
    context = {"w": 3, "mode": "test"}
    transition = sm.transition_to(
        KernelState.PRECONDITIONS_VALID,
        reason="With context",
        context=context,
        logged=True
    )
    assert transition.context["w"] == 3
    assert transition.context["mode"] == "test"


# ============================================================================
# NORMAL MODE CONTROLLER TESTS (Section 7.1)
# ============================================================================


def test_normal_mode_full_flow():
    """
    Test complete Normal Mode flow:
    IDLE → PRECONDITIONS_VALID → WIDTH_OK → AUTHORIZED → EXECUTING → COMPLETE → IDLE
    """
    sm = ClarityStateMachine()
    controller = NormalModeController(sm)

    context = StateMachineContext(
        mode=OperatingMode.NORMAL,
        w=2,
        invariants_satisfied=set(),
        has_authority=True
    )

    # IDLE → PRECONDITIONS_VALID
    controller.validate_preconditions(context, logged=True)
    assert sm.get_current_state() == KernelState.PRECONDITIONS_VALID

    # PRECONDITIONS_VALID → WIDTH_OK
    controller.validate_width(context, logged=True)
    assert sm.get_current_state() == KernelState.WIDTH_OK

    # WIDTH_OK → AUTHORIZED
    controller.authorize(context, logged=True)
    assert sm.get_current_state() == KernelState.AUTHORIZED

    # AUTHORIZED → EXECUTING
    controller.begin_execution(logged=True)
    assert sm.get_current_state() == KernelState.EXECUTING

    # EXECUTING → COMPLETE
    controller.complete(logged=True)
    assert sm.get_current_state() == KernelState.COMPLETE

    # COMPLETE → IDLE
    controller.reset(logged=True)
    assert sm.get_current_state() == KernelState.IDLE


def test_normal_mode_cannot_skip_steps():
    """Test that normal mode cannot skip state transitions."""
    sm = ClarityStateMachine()
    controller = NormalModeController(sm)

    # Try to authorize without validating preconditions
    with pytest.raises(InvalidStateTransition):
        context = StateMachineContext(
            mode=OperatingMode.NORMAL,
            w=2,
            invariants_satisfied=set(),
            has_authority=True
        )
        controller.authorize(context, logged=True)


# ============================================================================
# CONTINUOUS MODE CONTROLLER TESTS (Section 7.2)
# ============================================================================


def test_continuous_mode_requires_continuous_auth():
    """
    Test Continuous Authorization Mode flow:
    IDLE → PRECONDITIONS_VALID → WIDTH_OK → CONTINUOUS_AUTH_REQUIRED
    """
    sm = ClarityStateMachine()
    normal_controller = NormalModeController(sm)
    continuous_controller = ContinuousModeController(sm)

    context = StateMachineContext(
        mode=OperatingMode.CONTINUOUS,
        w=2,
        invariants_satisfied=set(),
        has_authority=True
    )

    # IDLE → PRECONDITIONS_VALID → WIDTH_OK
    normal_controller.validate_preconditions(context, logged=True)
    normal_controller.validate_width(context, logged=True)

    # WIDTH_OK → CONTINUOUS_AUTH_REQUIRED
    continuous_controller.require_continuous_auth(context, logged=True)
    assert sm.get_current_state() == KernelState.CONTINUOUS_AUTH_REQUIRED


def test_continuous_mode_execution_with_confirmation():
    """Test continuous mode execution with active confirmation."""
    sm = ClarityStateMachine()
    normal_controller = NormalModeController(sm)
    continuous_controller = ContinuousModeController(sm)

    context = StateMachineContext(
        mode=OperatingMode.CONTINUOUS,
        w=2,
        invariants_satisfied=set(),
        has_authority=True,
        confirmation_active=True
    )

    # Get to CONTINUOUS_AUTH_REQUIRED
    normal_controller.validate_preconditions(context, logged=True)
    normal_controller.validate_width(context, logged=True)
    continuous_controller.require_continuous_auth(context, logged=True)

    # CONTINUOUS_AUTH_REQUIRED → EXECUTING
    continuous_controller.begin_execution_with_confirmation(context, logged=True)
    assert sm.get_current_state() == KernelState.EXECUTING


def test_continuous_mode_immediate_stop():
    """Test that continuous mode can trigger immediate stop."""
    sm = ClarityStateMachine(initial_state=KernelState.EXECUTING)
    continuous_controller = ContinuousModeController(sm)

    # EXECUTING → IMMEDIATE_STOP
    continuous_controller.immediate_stop(
        reason="Confirmation lost",
        context={"trigger": "timeout"},
        logged=True
    )
    assert sm.get_current_state() == KernelState.IMMEDIATE_STOP


# ============================================================================
# ABNORMAL MODE CONTROLLER TESTS (Section 7.3)
# ============================================================================


def test_abnormal_mode_full_flow():
    """
    Test complete Abnormal/Override Mode flow:
    INVARIANT_UNSATISFIABLE → EXPLICIT_HUMAN_OVERRIDE → ABNORMAL_EXECUTION →
    PERSISTENT_WARNING → RESOLUTION → RETURN_TO_SAFE_STATE → IDLE
    """
    sm = ClarityStateMachine()
    abnormal_controller = AbnormalModeController(sm)

    # IDLE → INVARIANT_UNSATISFIABLE
    abnormal_controller.mark_unsatisfiable(["I-1", "I-7"], logged=True)
    assert sm.get_current_state() == KernelState.INVARIANT_UNSATISFIABLE

    # INVARIANT_UNSATISFIABLE → EXPLICIT_HUMAN_OVERRIDE
    abnormal_controller.apply_override("override_sig_12345", logged=True)
    assert sm.get_current_state() == KernelState.EXPLICIT_HUMAN_OVERRIDE

    # EXPLICIT_HUMAN_OVERRIDE → ABNORMAL_EXECUTION
    abnormal_controller.enter_abnormal_execution(logged=True)
    assert sm.get_current_state() == KernelState.ABNORMAL_EXECUTION

    # ABNORMAL_EXECUTION → PERSISTENT_WARNING
    abnormal_controller.show_persistent_warning(logged=True)
    assert sm.get_current_state() == KernelState.PERSISTENT_WARNING

    # PERSISTENT_WARNING → RESOLUTION
    abnormal_controller.resolve("Manual intervention", logged=True)
    assert sm.get_current_state() == KernelState.RESOLUTION

    # RESOLUTION → RETURN_TO_SAFE_STATE
    abnormal_controller.return_to_safe_state(logged=True)
    assert sm.get_current_state() == KernelState.RETURN_TO_SAFE_STATE

    # RETURN_TO_SAFE_STATE → IDLE
    abnormal_controller.reset(logged=True)
    assert sm.get_current_state() == KernelState.IDLE


def test_abnormal_mode_cannot_skip_override():
    """Test that abnormal mode requires explicit override."""
    sm = ClarityStateMachine()
    abnormal_controller = AbnormalModeController(sm)

    # Mark as unsatisfiable
    abnormal_controller.mark_unsatisfiable(["I-1"], logged=True)

    # Try to enter abnormal execution without override
    with pytest.raises(InvalidStateTransition):
        abnormal_controller.enter_abnormal_execution(logged=True)


# ============================================================================
# COMPLEX TRANSITION SCENARIOS
# ============================================================================


def test_transition_from_executing_to_immediate_stop():
    """Test that executing can transition to immediate stop."""
    sm = ClarityStateMachine(initial_state=KernelState.EXECUTING)
    continuous_controller = ContinuousModeController(sm)

    continuous_controller.immediate_stop(
        reason="Emergency stop",
        context={},
        logged=True
    )
    assert sm.get_current_state() == KernelState.IMMEDIATE_STOP


def test_transition_to_read_only_mode():
    """Test transition to READ_ONLY mode (degraded)."""
    sm = ClarityStateMachine()

    sm.transition_to(
        KernelState.READ_ONLY,
        reason="HIL unavailable",
        logged=True
    )
    assert sm.get_current_state() == KernelState.READ_ONLY


def test_read_only_can_return_to_idle():
    """Test that READ_ONLY can return to IDLE when HIL available."""
    sm = ClarityStateMachine(initial_state=KernelState.READ_ONLY)

    sm.transition_to(
        KernelState.IDLE,
        reason="HIL restored",
        logged=True
    )
    assert sm.get_current_state() == KernelState.IDLE


# ============================================================================
# STATE MACHINE CONTEXT TESTS
# ============================================================================


def test_state_machine_context_creation():
    """Test StateMachineContext creation."""
    context = StateMachineContext(
        mode=OperatingMode.NORMAL,
        w=2,
        invariants_satisfied={"I-1", "I-2"},
        has_authority=True,
        confirmation_active=False,
        override_signature=None
    )
    assert context.mode == OperatingMode.NORMAL
    assert context.w == 2
    assert "I-1" in context.invariants_satisfied
    assert context.has_authority
    assert not context.confirmation_active


def test_state_machine_context_with_override():
    """Test StateMachineContext with override signature."""
    context = StateMachineContext(
        mode=OperatingMode.ABNORMAL,
        w=5,
        invariants_satisfied=set(),
        has_authority=True,
        override_signature="override_abc123"
    )
    assert context.mode == OperatingMode.ABNORMAL
    assert context.override_signature == "override_abc123"


# ============================================================================
# STATE TRANSITION DATA STRUCTURE TESTS
# ============================================================================


def test_state_transition_attributes():
    """Test StateTransition data structure."""
    sm = ClarityStateMachine()
    transition = sm.transition_to(
        KernelState.PRECONDITIONS_VALID,
        reason="Test transition",
        context={"test": "data"},
        logged=True
    )

    assert transition.from_state == KernelState.IDLE
    assert transition.to_state == KernelState.PRECONDITIONS_VALID
    assert transition.reason == "Test transition"
    assert transition.context["test"] == "data"
    assert transition.timestamp is not None


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


def test_multiple_transitions_in_sequence():
    """Test multiple valid transitions in sequence."""
    sm = ClarityStateMachine()

    sm.transition_to(KernelState.PRECONDITIONS_VALID, "Step 1", logged=True)
    sm.transition_to(KernelState.WIDTH_OK, "Step 2", logged=True)
    sm.transition_to(KernelState.AUTHORIZED, "Step 3", logged=True)
    sm.transition_to(KernelState.EXECUTING, "Step 4", logged=True)

    assert sm.get_current_state() == KernelState.EXECUTING
    assert len(sm.get_transition_history()) == 4


def test_immediate_stop_from_various_states():
    """Test that IMMEDIATE_STOP can be reached from multiple states."""
    continuous_controller = ContinuousModeController(None)

    # From PRECONDITIONS_VALID
    sm1 = ClarityStateMachine(initial_state=KernelState.PRECONDITIONS_VALID)
    continuous_controller.sm = sm1
    continuous_controller.immediate_stop("Test", {}, logged=True)
    assert sm1.get_current_state() == KernelState.IMMEDIATE_STOP

    # From WIDTH_OK
    sm2 = ClarityStateMachine(initial_state=KernelState.WIDTH_OK)
    continuous_controller.sm = sm2
    continuous_controller.immediate_stop("Test", {}, logged=True)
    assert sm2.get_current_state() == KernelState.IMMEDIATE_STOP

    # From EXECUTING
    sm3 = ClarityStateMachine(initial_state=KernelState.EXECUTING)
    continuous_controller.sm = sm3
    continuous_controller.immediate_stop("Test", {}, logged=True)
    assert sm3.get_current_state() == KernelState.IMMEDIATE_STOP
