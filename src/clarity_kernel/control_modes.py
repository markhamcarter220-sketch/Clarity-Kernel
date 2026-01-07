"""
Clarity Kernel Control Modes (Section 6)

This module implements Momentary and Continuous authorization modes,
determining when and how human confirmation is required.

Critical semantics:
- Momentary: single authorization, strict preconditions
- Continuous: ongoing confirmation required, immediate stop on loss
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
from datetime import datetime, timedelta


# ============================================================================
# ENUMS
# ============================================================================


class ControlMode(Enum):
    """
    Control modes for authorization.

    MOMENTARY: Single authorization allows full execution
    CONTINUOUS: Ongoing confirmation required (deadman switch)
    """
    MOMENTARY = "momentary"
    CONTINUOUS = "continuous"


# ============================================================================
# EXCEPTIONS
# ============================================================================


class ControlModeViolation(Exception):
    """Base class for control mode violations."""
    pass


class MomentaryAuthorizationForbidden(ControlModeViolation):
    """
    Raised when momentary authorization is attempted but preconditions are not met.
    """

    def __init__(self, message: str, failed_conditions: list[str]):
        super().__init__(message)
        self.failed_conditions = failed_conditions


class ContinuousAuthorizationLost(ControlModeViolation):
    """
    Raised when continuous authorization confirmation is lost during execution.

    This triggers IMMEDIATE_STOP semantics (no partial completion).
    """

    def __init__(self, message: str, lost_at: datetime):
        super().__init__(message)
        self.lost_at = lost_at


class ContinuousAuthorizationRequired(ControlModeViolation):
    """
    Raised when momentary authorization is insufficient and continuous mode is required.
    """

    def __init__(self, message: str, triggering_conditions: list[str]):
        super().__init__(message)
        self.triggering_conditions = triggering_conditions


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class MomentaryPreconditions:
    """
    Preconditions that ALL must be true for momentary authorization.

    Attributes:
        outcome_reversible: Can the outcome be undone?
        risk_does_not_increase: Does risk remain constant over time?
        no_new_critical_info: Can critical info emerge during execution?
        w_within_limit: Is w ≤ 3 at authorization time?
        execution_window_bounded: Is execution time short and bounded?
    """
    outcome_reversible: bool
    risk_does_not_increase: bool
    no_new_critical_info: bool
    w_within_limit: bool
    execution_window_bounded: bool

    def all_satisfied(self) -> bool:
        """Returns True only if ALL preconditions are satisfied."""
        return (
            self.outcome_reversible
            and self.risk_does_not_increase
            and self.no_new_critical_info
            and self.w_within_limit
            and self.execution_window_bounded
        )

    def get_failed_conditions(self) -> list[str]:
        """Returns list of condition names that are not satisfied."""
        failed = []
        if not self.outcome_reversible:
            failed.append("outcome_reversible")
        if not self.risk_does_not_increase:
            failed.append("risk_does_not_increase")
        if not self.no_new_critical_info:
            failed.append("no_new_critical_info")
        if not self.w_within_limit:
            failed.append("w_within_limit")
        if not self.execution_window_bounded:
            failed.append("execution_window_bounded")
        return failed


@dataclass(frozen=True)
class ContinuousTriggers:
    """
    Conditions where ANY being true requires continuous authorization.

    Attributes:
        outcome_irreversible: Is the outcome permanent?
        compliance_safety_exposure: Are there compliance/safety concerns?
        context_may_change: Can context change during execution?
        ambiguity_at_initiation: Does ambiguity exist at start?
        w_may_fluctuate: Can w change during execution?
        execution_window_extended: Is execution time long?
    """
    outcome_irreversible: bool
    compliance_safety_exposure: bool
    context_may_change: bool
    ambiguity_at_initiation: bool
    w_may_fluctuate: bool
    execution_window_extended: bool

    def any_triggered(self) -> bool:
        """Returns True if ANY trigger condition is met."""
        return (
            self.outcome_irreversible
            or self.compliance_safety_exposure
            or self.context_may_change
            or self.ambiguity_at_initiation
            or self.w_may_fluctuate
            or self.execution_window_extended
        )

    def get_triggered_conditions(self) -> list[str]:
        """Returns list of condition names that are triggered."""
        triggered = []
        if self.outcome_irreversible:
            triggered.append("outcome_irreversible")
        if self.compliance_safety_exposure:
            triggered.append("compliance_safety_exposure")
        if self.context_may_change:
            triggered.append("context_may_change")
        if self.ambiguity_at_initiation:
            triggered.append("ambiguity_at_initiation")
        if self.w_may_fluctuate:
            triggered.append("w_may_fluctuate")
        if self.execution_window_extended:
            triggered.append("execution_window_extended")
        return triggered


@dataclass
class ContinuousConfirmation:
    """
    Represents an active continuous authorization confirmation.

    Attributes:
        confirmed: Current confirmation state
        last_confirmed_at: Timestamp of last confirmation
        confirmation_timeout: Maximum time between confirmations
        check_callback: Optional function to check confirmation validity
    """
    confirmed: bool
    last_confirmed_at: datetime
    confirmation_timeout: timedelta
    check_callback: Optional[Callable[[], bool]] = None

    def is_valid(self) -> bool:
        """
        Checks if confirmation is still valid.

        Returns:
            True if confirmed and not timed out
        """
        if not self.confirmed:
            return False

        # Check timeout
        if datetime.now() - self.last_confirmed_at > self.confirmation_timeout:
            return False

        # Check callback if provided
        if self.check_callback is not None:
            return self.check_callback()

        return True

    def refresh(self) -> None:
        """Refreshes the confirmation timestamp."""
        self.confirmed = True
        self.last_confirmed_at = datetime.now()

    def revoke(self) -> None:
        """Immediately revokes confirmation."""
        self.confirmed = False


# ============================================================================
# CONTROL MODE VALIDATORS
# ============================================================================


def validate_momentary_authorization(preconditions: MomentaryPreconditions) -> None:
    """
    Validates that momentary authorization is permitted.

    Args:
        preconditions: The preconditions to check

    Raises:
        MomentaryAuthorizationForbidden: If any precondition is not satisfied
    """
    if not preconditions.all_satisfied():
        failed = preconditions.get_failed_conditions()
        raise MomentaryAuthorizationForbidden(
            f"Momentary authorization forbidden. Failed preconditions: {', '.join(failed)}",
            failed_conditions=failed
        )


def require_continuous_authorization(triggers: ContinuousTriggers) -> None:
    """
    Checks if continuous authorization is required based on trigger conditions.

    Args:
        triggers: The trigger conditions to evaluate

    Raises:
        ContinuousAuthorizationRequired: If any trigger condition is met
    """
    if triggers.any_triggered():
        triggered = triggers.get_triggered_conditions()
        raise ContinuousAuthorizationRequired(
            f"Continuous authorization required. Triggering conditions: {', '.join(triggered)}",
            triggering_conditions=triggered
        )


def validate_continuous_confirmation(confirmation: ContinuousConfirmation) -> None:
    """
    Validates that continuous authorization confirmation is still valid.

    CRITICAL: This implements IMMEDIATE_STOP semantics.
    If confirmation is lost, execution MUST halt immediately.

    Args:
        confirmation: The confirmation state to check

    Raises:
        ContinuousAuthorizationLost: If confirmation is no longer valid
    """
    if not confirmation.is_valid():
        raise ContinuousAuthorizationLost(
            "Continuous authorization confirmation lost. IMMEDIATE STOP required.",
            lost_at=datetime.now()
        )


# ============================================================================
# CONTROL MODE SELECTION
# ============================================================================


def determine_control_mode(
    preconditions: MomentaryPreconditions,
    triggers: ContinuousTriggers
) -> ControlMode:
    """
    Determines the required control mode for an operation.

    Logic:
    1. If ANY continuous trigger is met → CONTINUOUS (overrides momentary)
    2. If ALL momentary preconditions satisfied → MOMENTARY
    3. Otherwise → CONTINUOUS (fail-safe)

    Args:
        preconditions: Momentary authorization preconditions
        triggers: Continuous authorization triggers

    Returns:
        The required ControlMode
    """
    # Continuous triggers override momentary preconditions
    if triggers.any_triggered():
        return ControlMode.CONTINUOUS

    # Only allow momentary if ALL preconditions are satisfied
    if preconditions.all_satisfied():
        return ControlMode.MOMENTARY

    # Fail-safe: default to continuous
    return ControlMode.CONTINUOUS


# ============================================================================
# EXECUTION GUARDS
# ============================================================================


class MomentaryExecutionGuard:
    """
    Guard for momentary authorization mode.

    Validates preconditions before allowing execution to proceed.
    """

    def __init__(self, preconditions: MomentaryPreconditions):
        self.preconditions = preconditions
        self.authorized = False

    def authorize(self) -> None:
        """
        Authorizes execution if preconditions are met.

        Raises:
            MomentaryAuthorizationForbidden: If preconditions not satisfied
        """
        validate_momentary_authorization(self.preconditions)
        self.authorized = True

    def check_authorized(self) -> None:
        """
        Checks that authorization was granted.

        Raises:
            ControlModeViolation: If not authorized
        """
        if not self.authorized:
            raise ControlModeViolation("Execution not authorized")


class ContinuousExecutionGuard:
    """
    Guard for continuous authorization mode.

    Maintains ongoing confirmation and enforces immediate stop on loss.
    """

    def __init__(
        self,
        confirmation_timeout: timedelta = timedelta(seconds=30),
        check_callback: Optional[Callable[[], bool]] = None
    ):
        self.confirmation = ContinuousConfirmation(
            confirmed=False,
            last_confirmed_at=datetime.now(),
            confirmation_timeout=confirmation_timeout,
            check_callback=check_callback
        )

    def authorize(self) -> None:
        """Grants initial authorization."""
        self.confirmation.refresh()

    def check_confirmation(self) -> None:
        """
        Checks that confirmation is still valid.

        CRITICAL: Raises exception immediately if confirmation lost.
        No partial completion allowed.

        Raises:
            ContinuousAuthorizationLost: If confirmation is no longer valid
        """
        validate_continuous_confirmation(self.confirmation)

    def refresh_confirmation(self) -> None:
        """Refreshes the confirmation (called by HIL)."""
        self.confirmation.refresh()

    def revoke(self) -> None:
        """Immediately revokes authorization."""
        self.confirmation.revoke()
