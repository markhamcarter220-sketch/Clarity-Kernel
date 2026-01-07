"""
Clarity Kernel State Machine (Section 7)

This module implements the three state machines defined in the specification:
1. Normal Mode (momentary authorization)
2. Continuous Authorization Mode
3. Abnormal/Override Mode (break-glass)

Critical requirement: No silent transitions are permitted.
All state changes must be explicit and logged.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set
from datetime import datetime


# ============================================================================
# STATE ENUMS
# ============================================================================


class KernelState(Enum):
    """All possible kernel states across all operating modes."""

    # Normal mode states
    IDLE = "IDLE"
    PRECONDITIONS_VALID = "PRECONDITIONS_VALID"
    WIDTH_OK = "WIDTH_OK"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"

    # Continuous authorization mode states
    CONTINUOUS_AUTH_REQUIRED = "CONTINUOUS_AUTH_REQUIRED"
    IMMEDIATE_STOP = "IMMEDIATE_STOP"

    # Abnormal/override mode states
    INVARIANT_UNSATISFIABLE = "INVARIANT_UNSATISFIABLE"
    EXPLICIT_HUMAN_OVERRIDE = "EXPLICIT_HUMAN_OVERRIDE"
    ABNORMAL_EXECUTION = "ABNORMAL_EXECUTION"
    PERSISTENT_WARNING = "PERSISTENT_WARNING"
    RESOLUTION = "RESOLUTION"
    RETURN_TO_SAFE_STATE = "RETURN_TO_SAFE_STATE"

    # Degraded mode state
    READ_ONLY = "READ_ONLY"


class OperatingMode(Enum):
    """High-level operating modes."""
    NORMAL = "NORMAL"
    CONTINUOUS = "CONTINUOUS"
    ABNORMAL = "ABNORMAL"
    DEGRADED = "DEGRADED"


# ============================================================================
# EXCEPTIONS
# ============================================================================


class InvalidStateTransition(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: KernelState, to_state: KernelState, reason: str):
        super().__init__(
            f"Invalid transition from {from_state.value} to {to_state.value}: {reason}"
        )
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


class SilentTransitionAttempt(Exception):
    """
    Raised when a state transition is attempted without proper logging/notification.

    Per spec: "No silent transitions are permitted."
    """

    def __init__(self, from_state: KernelState, to_state: KernelState):
        super().__init__(
            f"Silent transition attempted from {from_state.value} to {to_state.value}"
        )
        self.from_state = from_state
        self.to_state = to_state


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class StateTransition:
    """
    Represents a state transition with full context.

    Attributes:
        from_state: Starting state
        to_state: Target state
        timestamp: When transition occurred
        reason: Explanation for transition
        context: Additional context data
    """
    from_state: KernelState
    to_state: KernelState
    timestamp: datetime
    reason: str
    context: dict


@dataclass
class StateMachineContext:
    """
    Context carried through state machine execution.

    Attributes:
        mode: Current operating mode
        w: Current interface width
        invariants_satisfied: Set of satisfied invariant IDs
        has_authority: Whether authorization is present
        confirmation_active: Whether continuous confirmation is active
        override_signature: Override authorization (if in abnormal mode)
    """
    mode: OperatingMode
    w: int
    invariants_satisfied: Set[str]
    has_authority: bool
    confirmation_active: bool = False
    override_signature: Optional[str] = None


# ============================================================================
# STATE MACHINE IMPLEMENTATION
# ============================================================================


class ClarityStateMachine:
    """
    Implements the Clarity Kernel state machine.

    Enforces valid transitions and prevents silent state changes.
    """

    def __init__(self, initial_state: KernelState = KernelState.IDLE):
        self.current_state = initial_state
        self.transition_history: list[StateTransition] = []
        self._transition_logged = False

        # Define valid transitions for each state
        self._valid_transitions = self._build_transition_table()

    def _build_transition_table(self) -> dict[KernelState, Set[KernelState]]:
        """
        Builds the valid state transition table.

        Returns:
            Dictionary mapping each state to its valid next states
        """
        return {
            # Normal mode transitions
            KernelState.IDLE: {
                KernelState.PRECONDITIONS_VALID,
                KernelState.INVARIANT_UNSATISFIABLE,
                KernelState.READ_ONLY
            },
            KernelState.PRECONDITIONS_VALID: {
                KernelState.WIDTH_OK,
                KernelState.INVARIANT_UNSATISFIABLE,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.WIDTH_OK: {
                KernelState.AUTHORIZED,
                KernelState.CONTINUOUS_AUTH_REQUIRED,
                KernelState.INVARIANT_UNSATISFIABLE,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.AUTHORIZED: {
                KernelState.EXECUTING,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.EXECUTING: {
                KernelState.COMPLETE,
                KernelState.IMMEDIATE_STOP,
                KernelState.INVARIANT_UNSATISFIABLE
            },
            KernelState.COMPLETE: {
                KernelState.IDLE
            },

            # Continuous authorization mode transitions
            KernelState.CONTINUOUS_AUTH_REQUIRED: {
                KernelState.EXECUTING,
                KernelState.IMMEDIATE_STOP,
                KernelState.INVARIANT_UNSATISFIABLE
            },
            KernelState.IMMEDIATE_STOP: {
                KernelState.IDLE,
                KernelState.INVARIANT_UNSATISFIABLE,
                KernelState.RESOLUTION
            },

            # Abnormal/override mode transitions
            KernelState.INVARIANT_UNSATISFIABLE: {
                KernelState.EXPLICIT_HUMAN_OVERRIDE,
                KernelState.IMMEDIATE_STOP,
                KernelState.READ_ONLY
            },
            KernelState.EXPLICIT_HUMAN_OVERRIDE: {
                KernelState.ABNORMAL_EXECUTION,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.ABNORMAL_EXECUTION: {
                KernelState.PERSISTENT_WARNING,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.PERSISTENT_WARNING: {
                KernelState.RESOLUTION,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.RESOLUTION: {
                KernelState.RETURN_TO_SAFE_STATE,
                KernelState.IMMEDIATE_STOP
            },
            KernelState.RETURN_TO_SAFE_STATE: {
                KernelState.IDLE
            },

            # Degraded mode transitions
            KernelState.READ_ONLY: {
                KernelState.IDLE  # Only when HIL becomes available again
            }
        }

    def can_transition_to(self, target_state: KernelState) -> bool:
        """
        Checks if transition to target state is valid from current state.

        Args:
            target_state: The state to transition to

        Returns:
            True if transition is valid
        """
        valid_next_states = self._valid_transitions.get(self.current_state, set())
        return target_state in valid_next_states

    def transition_to(
        self,
        target_state: KernelState,
        reason: str,
        context: Optional[dict] = None,
        logged: bool = False
    ) -> StateTransition:
        """
        Transitions to a new state.

        CRITICAL: This method enforces:
        1. Valid state transitions only
        2. No silent transitions (must be logged)

        Args:
            target_state: The state to transition to
            reason: Explanation for the transition (required, never empty)
            context: Additional context data
            logged: Whether this transition has been logged (caller responsibility)

        Returns:
            The StateTransition record

        Raises:
            InvalidStateTransition: If transition is not valid
            SilentTransitionAttempt: If transition not logged
            ValueError: If reason is empty
        """
        if not reason or not reason.strip():
            raise ValueError("Transition reason cannot be empty")

        # Check if transition is valid
        if not self.can_transition_to(target_state):
            raise InvalidStateTransition(
                self.current_state,
                target_state,
                f"Not in valid transitions: {self._valid_transitions.get(self.current_state, set())}"
            )

        # Enforce no silent transitions
        if not logged:
            raise SilentTransitionAttempt(self.current_state, target_state)

        # Create transition record
        transition = StateTransition(
            from_state=self.current_state,
            to_state=target_state,
            timestamp=datetime.now(),
            reason=reason,
            context=context or {}
        )

        # Execute transition
        self.current_state = target_state
        self.transition_history.append(transition)

        return transition

    def get_current_state(self) -> KernelState:
        """Returns the current state."""
        return self.current_state

    def get_transition_history(self) -> list[StateTransition]:
        """Returns the full transition history (immutable)."""
        return self.transition_history.copy()


# ============================================================================
# MODE-SPECIFIC STATE MACHINE CONTROLLERS
# ============================================================================


class NormalModeController:
    """
    Controls state transitions for Normal Mode (Section 7.1).

    State flow:
    IDLE → PRECONDITIONS_VALID → WIDTH_OK → AUTHORIZED → EXECUTING → COMPLETE
    """

    def __init__(self, state_machine: ClarityStateMachine):
        self.sm = state_machine

    def validate_preconditions(self, context: StateMachineContext, logged: bool) -> None:
        """Transition: IDLE → PRECONDITIONS_VALID"""
        self.sm.transition_to(
            KernelState.PRECONDITIONS_VALID,
            "Preconditions validated for normal mode execution",
            context={"mode": context.mode.value},
            logged=logged
        )

    def validate_width(self, context: StateMachineContext, logged: bool) -> None:
        """Transition: PRECONDITIONS_VALID → WIDTH_OK"""
        self.sm.transition_to(
            KernelState.WIDTH_OK,
            f"Interface width w={context.w} is within limit (≤ 3)",
            context={"w": context.w},
            logged=logged
        )

    def authorize(self, context: StateMachineContext, logged: bool) -> None:
        """Transition: WIDTH_OK → AUTHORIZED"""
        self.sm.transition_to(
            KernelState.AUTHORIZED,
            "Momentary authorization granted",
            context={"has_authority": context.has_authority},
            logged=logged
        )

    def begin_execution(self, logged: bool) -> None:
        """Transition: AUTHORIZED → EXECUTING"""
        self.sm.transition_to(
            KernelState.EXECUTING,
            "Beginning execution under momentary authorization",
            logged=logged
        )

    def complete(self, logged: bool) -> None:
        """Transition: EXECUTING → COMPLETE"""
        self.sm.transition_to(
            KernelState.COMPLETE,
            "Execution completed successfully",
            logged=logged
        )

    def reset(self, logged: bool) -> None:
        """Transition: COMPLETE → IDLE"""
        self.sm.transition_to(
            KernelState.IDLE,
            "Returning to idle state",
            logged=logged
        )


class ContinuousModeController:
    """
    Controls state transitions for Continuous Authorization Mode (Section 7.2).

    State flow:
    IDLE → PRECONDITIONS_VALID → WIDTH_OK → CONTINUOUS_AUTH_REQUIRED →
    EXECUTING (confirmation maintained) → IMMEDIATE_STOP (on loss)
    """

    def __init__(self, state_machine: ClarityStateMachine):
        self.sm = state_machine

    def require_continuous_auth(self, context: StateMachineContext, logged: bool) -> None:
        """Transition: WIDTH_OK → CONTINUOUS_AUTH_REQUIRED"""
        self.sm.transition_to(
            KernelState.CONTINUOUS_AUTH_REQUIRED,
            "Continuous authorization required for this operation",
            context={"mode": context.mode.value},
            logged=logged
        )

    def begin_execution_with_confirmation(self, context: StateMachineContext, logged: bool) -> None:
        """Transition: CONTINUOUS_AUTH_REQUIRED → EXECUTING"""
        self.sm.transition_to(
            KernelState.EXECUTING,
            "Beginning execution under continuous authorization",
            context={"confirmation_active": context.confirmation_active},
            logged=logged
        )

    def immediate_stop(self, reason: str, context: Optional[dict], logged: bool) -> None:
        """
        Transition: EXECUTING → IMMEDIATE_STOP

        Triggers:
        - confirmation lost
        - w becomes >3
        - invariant violation
        """
        self.sm.transition_to(
            KernelState.IMMEDIATE_STOP,
            f"IMMEDIATE STOP triggered: {reason}",
            context=context,
            logged=logged
        )


class AbnormalModeController:
    """
    Controls state transitions for Abnormal/Override Mode (Section 7.3).

    State flow:
    INVARIANT_UNSATISFIABLE → EXPLICIT_HUMAN_OVERRIDE → ABNORMAL_EXECUTION →
    PERSISTENT_WARNING → RESOLUTION → RETURN_TO_SAFE_STATE
    """

    def __init__(self, state_machine: ClarityStateMachine):
        self.sm = state_machine

    def mark_unsatisfiable(self, invariant_ids: list[str], logged: bool) -> None:
        """Transition: * → INVARIANT_UNSATISFIABLE"""
        self.sm.transition_to(
            KernelState.INVARIANT_UNSATISFIABLE,
            f"Invariants unsatisfiable: {', '.join(invariant_ids)}",
            context={"unsatisfiable_invariants": invariant_ids},
            logged=logged
        )

    def apply_override(self, override_signature: str, logged: bool) -> None:
        """Transition: INVARIANT_UNSATISFIABLE → EXPLICIT_HUMAN_OVERRIDE"""
        self.sm.transition_to(
            KernelState.EXPLICIT_HUMAN_OVERRIDE,
            "Human override explicitly applied (break-glass)",
            context={"override_signature": override_signature},
            logged=logged
        )

    def enter_abnormal_execution(self, logged: bool) -> None:
        """Transition: EXPLICIT_HUMAN_OVERRIDE → ABNORMAL_EXECUTION"""
        self.sm.transition_to(
            KernelState.ABNORMAL_EXECUTION,
            "Entering abnormal execution mode",
            logged=logged
        )

    def show_persistent_warning(self, logged: bool) -> None:
        """Transition: ABNORMAL_EXECUTION → PERSISTENT_WARNING"""
        self.sm.transition_to(
            KernelState.PERSISTENT_WARNING,
            "Persistent warning active (abnormal mode)",
            logged=logged
        )

    def resolve(self, resolution_method: str, logged: bool) -> None:
        """Transition: PERSISTENT_WARNING → RESOLUTION"""
        self.sm.transition_to(
            KernelState.RESOLUTION,
            f"Resolving abnormal state: {resolution_method}",
            context={"resolution_method": resolution_method},
            logged=logged
        )

    def return_to_safe_state(self, logged: bool) -> None:
        """Transition: RESOLUTION → RETURN_TO_SAFE_STATE"""
        self.sm.transition_to(
            KernelState.RETURN_TO_SAFE_STATE,
            "Returning to safe state from abnormal mode",
            logged=logged
        )

    def reset(self, logged: bool) -> None:
        """Transition: RETURN_TO_SAFE_STATE → IDLE"""
        self.sm.transition_to(
            KernelState.IDLE,
            "Abnormal mode resolved, returning to idle",
            logged=logged
        )
