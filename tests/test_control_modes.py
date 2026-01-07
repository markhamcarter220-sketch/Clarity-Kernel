"""
Test Suite for Clarity Kernel Control Modes

Tests Momentary vs Continuous authorization modes (Section 6):
- Momentary: single authorization, strict preconditions
- Continuous: ongoing confirmation required, immediate stop on loss
"""

import pytest
from datetime import datetime, timedelta
from clarity_kernel.control_modes import (
    ControlMode,
    MomentaryPreconditions,
    ContinuousTriggers,
    ContinuousConfirmation,
    MomentaryExecutionGuard,
    ContinuousExecutionGuard,
    validate_momentary_authorization,
    require_continuous_authorization,
    validate_continuous_confirmation,
    determine_control_mode,
    MomentaryAuthorizationForbidden,
    ContinuousAuthorizationLost,
    ContinuousAuthorizationRequired,
)


# ============================================================================
# MOMENTARY PRECONDITIONS TESTS
# ============================================================================


def test_momentary_preconditions_all_satisfied():
    """Test that all_satisfied returns True when all conditions are met."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    assert preconditions.all_satisfied()
    assert len(preconditions.get_failed_conditions()) == 0


def test_momentary_preconditions_one_failed():
    """Test that all_satisfied returns False when one condition fails."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=False,  # FAILED
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    assert not preconditions.all_satisfied()
    assert "outcome_reversible" in preconditions.get_failed_conditions()


def test_momentary_preconditions_multiple_failed():
    """Test that get_failed_conditions returns all failed conditions."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=False,
        risk_does_not_increase=False,
        no_new_critical_info=True,
        w_within_limit=False,
        execution_window_bounded=True
    )
    failed = preconditions.get_failed_conditions()
    assert "outcome_reversible" in failed
    assert "risk_does_not_increase" in failed
    assert "w_within_limit" in failed
    assert len(failed) == 3


# ============================================================================
# CONTINUOUS TRIGGERS TESTS
# ============================================================================


def test_continuous_triggers_none_triggered():
    """Test that any_triggered returns False when no triggers are met."""
    triggers = ContinuousTriggers(
        outcome_irreversible=False,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    assert not triggers.any_triggered()
    assert len(triggers.get_triggered_conditions()) == 0


def test_continuous_triggers_one_triggered():
    """Test that any_triggered returns True when one trigger is met."""
    triggers = ContinuousTriggers(
        outcome_irreversible=True,  # TRIGGERED
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    assert triggers.any_triggered()
    assert "outcome_irreversible" in triggers.get_triggered_conditions()


def test_continuous_triggers_multiple_triggered():
    """Test that get_triggered_conditions returns all triggered conditions."""
    triggers = ContinuousTriggers(
        outcome_irreversible=True,
        compliance_safety_exposure=True,
        context_may_change=False,
        ambiguity_at_initiation=True,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    triggered = triggers.get_triggered_conditions()
    assert "outcome_irreversible" in triggered
    assert "compliance_safety_exposure" in triggered
    assert "ambiguity_at_initiation" in triggered
    assert len(triggered) == 3


# ============================================================================
# VALIDATE MOMENTARY AUTHORIZATION TESTS
# ============================================================================


def test_validate_momentary_passes_when_all_satisfied():
    """Test that validation passes when all preconditions are satisfied."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    validate_momentary_authorization(preconditions)
    # No exception = pass


def test_validate_momentary_fails_when_preconditions_not_met():
    """Test that validation fails when preconditions are not met."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=False,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    with pytest.raises(MomentaryAuthorizationForbidden) as exc_info:
        validate_momentary_authorization(preconditions)
    assert "outcome_reversible" in exc_info.value.failed_conditions


# ============================================================================
# REQUIRE CONTINUOUS AUTHORIZATION TESTS
# ============================================================================


def test_require_continuous_does_not_raise_when_no_triggers():
    """Test that continuous authorization is not required when no triggers."""
    triggers = ContinuousTriggers(
        outcome_irreversible=False,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    require_continuous_authorization(triggers)
    # No exception = continuous not required


def test_require_continuous_raises_when_triggers_present():
    """Test that continuous authorization is required when triggers are present."""
    triggers = ContinuousTriggers(
        outcome_irreversible=True,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    with pytest.raises(ContinuousAuthorizationRequired) as exc_info:
        require_continuous_authorization(triggers)
    assert "outcome_irreversible" in exc_info.value.triggering_conditions


# ============================================================================
# CONTINUOUS CONFIRMATION TESTS
# ============================================================================


def test_continuous_confirmation_is_valid_when_confirmed():
    """Test that confirmation is valid when confirmed and not timed out."""
    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30)
    )
    assert confirmation.is_valid()


def test_continuous_confirmation_is_invalid_when_not_confirmed():
    """Test that confirmation is invalid when not confirmed."""
    confirmation = ContinuousConfirmation(
        confirmed=False,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30)
    )
    assert not confirmation.is_valid()


def test_continuous_confirmation_is_invalid_when_timed_out():
    """Test that confirmation is invalid when timed out."""
    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now() - timedelta(seconds=60),
        confirmation_timeout=timedelta(seconds=30)
    )
    assert not confirmation.is_valid()


def test_continuous_confirmation_refresh():
    """Test that refresh updates confirmation state."""
    confirmation = ContinuousConfirmation(
        confirmed=False,
        last_confirmed_at=datetime.now() - timedelta(seconds=60),
        confirmation_timeout=timedelta(seconds=30)
    )
    confirmation.refresh()
    assert confirmation.confirmed
    assert confirmation.is_valid()


def test_continuous_confirmation_revoke():
    """Test that revoke immediately invalidates confirmation."""
    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30)
    )
    confirmation.revoke()
    assert not confirmation.confirmed
    assert not confirmation.is_valid()


def test_continuous_confirmation_callback():
    """Test that callback is used for validation."""
    callback_result = True

    def check_callback():
        return callback_result

    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30),
        check_callback=check_callback
    )
    assert confirmation.is_valid()

    callback_result = False
    assert not confirmation.is_valid()


# ============================================================================
# VALIDATE CONTINUOUS CONFIRMATION TESTS
# ============================================================================


def test_validate_continuous_confirmation_passes_when_valid():
    """Test that validation passes when confirmation is valid."""
    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30)
    )
    validate_continuous_confirmation(confirmation)
    # No exception = pass


def test_validate_continuous_confirmation_fails_when_invalid():
    """Test that validation fails when confirmation is invalid."""
    confirmation = ContinuousConfirmation(
        confirmed=False,
        last_confirmed_at=datetime.now(),
        confirmation_timeout=timedelta(seconds=30)
    )
    with pytest.raises(ContinuousAuthorizationLost) as exc_info:
        validate_continuous_confirmation(confirmation)
    assert "IMMEDIATE STOP" in str(exc_info.value)


def test_validate_continuous_confirmation_fails_when_timed_out():
    """Test that validation fails when confirmation times out."""
    confirmation = ContinuousConfirmation(
        confirmed=True,
        last_confirmed_at=datetime.now() - timedelta(seconds=60),
        confirmation_timeout=timedelta(seconds=30)
    )
    with pytest.raises(ContinuousAuthorizationLost):
        validate_continuous_confirmation(confirmation)


# ============================================================================
# DETERMINE CONTROL MODE TESTS
# ============================================================================


def test_determine_control_mode_returns_momentary_when_all_conditions_met():
    """Test that momentary mode is selected when all preconditions met and no triggers."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    triggers = ContinuousTriggers(
        outcome_irreversible=False,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    mode = determine_control_mode(preconditions, triggers)
    assert mode == ControlMode.MOMENTARY


def test_determine_control_mode_returns_continuous_when_triggers_present():
    """Test that continuous mode is selected when triggers are present (overrides momentary)."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    triggers = ContinuousTriggers(
        outcome_irreversible=True,  # TRIGGER PRESENT
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    mode = determine_control_mode(preconditions, triggers)
    assert mode == ControlMode.CONTINUOUS


def test_determine_control_mode_returns_continuous_when_preconditions_failed():
    """Test that continuous mode is selected when preconditions fail (fail-safe)."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=False,  # FAILED
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    triggers = ContinuousTriggers(
        outcome_irreversible=False,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )
    mode = determine_control_mode(preconditions, triggers)
    assert mode == ControlMode.CONTINUOUS


# ============================================================================
# MOMENTARY EXECUTION GUARD TESTS
# ============================================================================


def test_momentary_guard_authorize_succeeds_when_preconditions_met():
    """Test that momentary guard can be authorized when preconditions are met."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    guard = MomentaryExecutionGuard(preconditions)
    guard.authorize()
    assert guard.authorized


def test_momentary_guard_authorize_fails_when_preconditions_not_met():
    """Test that momentary guard authorization fails when preconditions are not met."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=False,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    guard = MomentaryExecutionGuard(preconditions)
    with pytest.raises(MomentaryAuthorizationForbidden):
        guard.authorize()


def test_momentary_guard_check_authorized_fails_when_not_authorized():
    """Test that check_authorized fails when not authorized."""
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,
        risk_does_not_increase=True,
        no_new_critical_info=True,
        w_within_limit=True,
        execution_window_bounded=True
    )
    guard = MomentaryExecutionGuard(preconditions)
    with pytest.raises(Exception):  # ControlModeViolation
        guard.check_authorized()


# ============================================================================
# CONTINUOUS EXECUTION GUARD TESTS
# ============================================================================


def test_continuous_guard_authorize():
    """Test that continuous guard can be authorized."""
    guard = ContinuousExecutionGuard()
    guard.authorize()
    assert guard.confirmation.confirmed
    assert guard.confirmation.is_valid()


def test_continuous_guard_check_confirmation_passes_when_valid():
    """Test that check_confirmation passes when confirmation is valid."""
    guard = ContinuousExecutionGuard()
    guard.authorize()
    guard.check_confirmation()
    # No exception = pass


def test_continuous_guard_check_confirmation_fails_when_not_authorized():
    """Test that check_confirmation fails when not authorized."""
    guard = ContinuousExecutionGuard()
    # Never authorized
    with pytest.raises(ContinuousAuthorizationLost):
        guard.check_confirmation()


def test_continuous_guard_refresh_confirmation():
    """Test that refresh_confirmation updates the confirmation state."""
    guard = ContinuousExecutionGuard()
    guard.authorize()
    old_time = guard.confirmation.last_confirmed_at
    guard.refresh_confirmation()
    new_time = guard.confirmation.last_confirmed_at
    assert new_time >= old_time


def test_continuous_guard_revoke():
    """Test that revoke immediately invalidates confirmation."""
    guard = ContinuousExecutionGuard()
    guard.authorize()
    guard.revoke()
    with pytest.raises(ContinuousAuthorizationLost):
        guard.check_confirmation()


def test_continuous_guard_check_fails_after_timeout():
    """Test that check fails when confirmation times out."""
    guard = ContinuousExecutionGuard(confirmation_timeout=timedelta(milliseconds=1))
    guard.authorize()
    import time
    time.sleep(0.01)  # Wait for timeout
    with pytest.raises(ContinuousAuthorizationLost):
        guard.check_confirmation()
