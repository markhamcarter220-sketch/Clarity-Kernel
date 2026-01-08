"""
Clarity Kernel Immutable Audit Logging (Section 13)

This module implements append-only, immutable audit logging for all kernel events.

Critical requirements (I-5: Logging Invariant):
- Every invariant violation or bypass attempt must be logged
- Nothing is silently suppressed
- All logs are immutable (append-only)
- Full context retained for every event

Per spec Section 13, all events must log:
- timestamp
- kernel state
- invariants evaluated (pass/fail)
- measured w and variable list
- authority source / identity
- control mode
- duration in state
- resolution outcome
- SSL version
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import json
from pathlib import Path


# ============================================================================
# CONSTANTS
# ============================================================================

SSL_VERSION = "v1.2.0"  # Must match SPECIFICATION.md


# ============================================================================
# ENUMS
# ============================================================================


class EventType(Enum):
    """Types of events that must be logged."""
    INVARIANT_VIOLATION = "invariant_violation"
    BYPASS_ATTEMPT = "bypass_attempt"
    STATE_TRANSITION = "state_transition"
    AUTHORIZATION_GRANTED = "authorization_granted"
    AUTHORIZATION_DENIED = "authorization_denied"
    OVERRIDE_APPLIED = "override_applied"
    IMMEDIATE_STOP = "immediate_stop"
    WIDTH_EVALUATION = "width_evaluation"
    DECOMPOSITION_ATTEMPT = "decomposition_attempt"
    ESCALATION = "escalation"
    LTC_TRANSFER_EVALUATED = "ltc_transfer_evaluated"


class ResolutionOutcome(Enum):
    """Possible outcomes of a permission gate."""
    PROCEED = "proceed"
    STOP = "stop"
    ESCALATE = "escalate"
    OVERRIDE = "override"
    DECOMPOSE = "decompose"


class DecompositionStatus(Enum):
    """Status of decomposition attempt (Section 8.5)."""
    NOT_ATTEMPTED = "not_attempted"
    ATTEMPTED = "attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ============================================================================
# EXCEPTIONS
# ============================================================================


class LogSuppressionAttempt(Exception):
    """
    Raised when an attempt to suppress logging is detected.

    This is a critical violation of I-5: Logging Invariant.
    """

    def __init__(self, message: str, attempted_event: str):
        super().__init__(message)
        self.attempted_event = attempted_event


class LogMutationAttempt(Exception):
    """
    Raised when an attempt to mutate existing logs is detected.

    Logs are append-only and immutable.
    """

    def __init__(self, message: str):
        super().__init__(message)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class LogEntry:
    """
    Immutable audit log entry.

    Contains all required fields per Section 13.
    """
    # Required core fields
    timestamp: datetime
    event_type: EventType
    kernel_state: str
    ssl_version: str

    # Invariant tracking
    invariants_evaluated: dict[str, bool]  # invariant_id -> pass/fail

    # Width tracking (Section 8.5)
    measured_w: Optional[int] = None
    unresolved_variables: list[str] = field(default_factory=list)
    decomposition_status: Optional[DecompositionStatus] = None

    # Authority tracking
    authority_source: Optional[str] = None  # or "unavailable"

    # Control mode
    control_mode: Optional[str] = None  # momentary / continuous / abnormal

    # State duration
    duration_in_state: Optional[float] = None  # seconds

    # Resolution
    resolution_outcome: Optional[ResolutionOutcome] = None

    # Additional context
    context: dict[str, Any] = field(default_factory=dict)

    # Message
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Converts log entry to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "kernel_state": self.kernel_state,
            "ssl_version": self.ssl_version,
            "invariants_evaluated": self.invariants_evaluated,
            "measured_w": self.measured_w,
            "unresolved_variables": self.unresolved_variables,
            "decomposition_status": self.decomposition_status.value if self.decomposition_status else None,
            "authority_source": self.authority_source,
            "control_mode": self.control_mode,
            "duration_in_state": self.duration_in_state,
            "resolution_outcome": self.resolution_outcome.value if self.resolution_outcome else None,
            "context": self.context,
            "message": self.message
        }

    def to_json(self) -> str:
        """Converts log entry to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# ============================================================================
# AUDIT LOGGER
# ============================================================================


class AuditLogger:
    """
    Immutable, append-only audit logger.

    CRITICAL PROPERTIES:
    - Logs are never deleted or modified
    - All events are captured
    - No silent suppression
    - Violations of logging invariant raise exceptions
    """

    def __init__(self, log_file: Optional[Path] = None, in_memory: bool = False):
        """
        Initializes the audit logger.

        Args:
            log_file: Path to append-only log file (None for no file logging)
            in_memory: Whether to keep logs in memory (always True for testing)
        """
        self._log_file = log_file
        self._in_memory = in_memory
        self._entries: list[LogEntry] = []
        self._suppression_detected = False

        # Create log file if specified
        if self._log_file:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self._log_file.exists():
                self._log_file.touch()

    def log(self, entry: LogEntry) -> None:
        """
        Appends an immutable log entry.

        Args:
            entry: The log entry to append

        Raises:
            LogSuppressionAttempt: If suppression is detected
        """
        if self._suppression_detected:
            raise LogSuppressionAttempt(
                "Log suppression previously detected, cannot continue logging",
                attempted_event=entry.event_type.value
            )

        # Append to in-memory log
        if self._in_memory:
            self._entries.append(entry)

        # Append to file log
        if self._log_file:
            try:
                with open(self._log_file, 'a') as f:
                    f.write(entry.to_json() + '\n')
            except Exception as e:
                # Logging failure is a critical error
                self._suppression_detected = True
                raise LogSuppressionAttempt(
                    f"Failed to write log entry: {e}",
                    attempted_event=entry.event_type.value
                ) from e

    def log_invariant_violation(
        self,
        invariant_id: str,
        kernel_state: str,
        message: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs an invariant violation.

        Args:
            invariant_id: The violated invariant (e.g., "I-1")
            kernel_state: Current kernel state
            message: Description of the violation
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.INVARIANT_VIOLATION,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={invariant_id: False},
            context=context or {},
            message=message
        )
        self.log(entry)

    def log_state_transition(
        self,
        from_state: str,
        to_state: str,
        reason: str,
        invariants_evaluated: dict[str, bool],
        measured_w: Optional[int] = None,
        control_mode: Optional[str] = None,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs a state transition.

        Args:
            from_state: Starting state
            to_state: Target state
            reason: Reason for transition
            invariants_evaluated: Invariants checked and their results
            measured_w: Interface width at transition
            control_mode: Active control mode
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.STATE_TRANSITION,
            kernel_state=to_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated=invariants_evaluated,
            measured_w=measured_w,
            control_mode=control_mode,
            context={
                "from_state": from_state,
                "to_state": to_state,
                **(context or {})
            },
            message=reason
        )
        self.log(entry)

    def log_width_evaluation(
        self,
        measured_w: int,
        unresolved_variables: list[str],
        kernel_state: str,
        decomposition_status: DecompositionStatus,
        resolution_outcome: ResolutionOutcome,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs a width evaluation (Section 8.5).

        Args:
            measured_w: The measured interface width
            unresolved_variables: List of unresolved material variables
            kernel_state: Current kernel state
            decomposition_status: Status of decomposition attempt
            resolution_outcome: How the width issue was resolved
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.WIDTH_EVALUATION,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={"I-7": measured_w <= 3},
            measured_w=measured_w,
            unresolved_variables=unresolved_variables,
            decomposition_status=decomposition_status,
            resolution_outcome=resolution_outcome,
            context=context or {},
            message=f"Width evaluation: w={measured_w}, outcome={resolution_outcome.value}"
        )
        self.log(entry)

    def log_authorization(
        self,
        granted: bool,
        authority_source: str,
        required_scope: str,
        kernel_state: str,
        control_mode: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs an authorization decision.

        Args:
            granted: Whether authorization was granted
            authority_source: Source of authority
            required_scope: Scope that was required
            kernel_state: Current kernel state
            control_mode: Control mode being used
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.AUTHORIZATION_GRANTED if granted else EventType.AUTHORIZATION_DENIED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={"I-2": granted},
            authority_source=authority_source,
            control_mode=control_mode,
            context={"required_scope": required_scope, **(context or {})},
            message=f"Authorization {'granted' if granted else 'denied'} for scope: {required_scope}"
        )
        self.log(entry)

    def log_override(
        self,
        override_signature: str,
        unsatisfiable_invariants: list[str],
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs a break-glass override.

        Args:
            override_signature: The override authorization signature
            unsatisfiable_invariants: Which invariants are being overridden
            kernel_state: Current kernel state
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.OVERRIDE_APPLIED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={inv: False for inv in unsatisfiable_invariants},
            authority_source=override_signature,
            control_mode="abnormal",
            resolution_outcome=ResolutionOutcome.OVERRIDE,
            context=context or {},
            message=f"Override applied for invariants: {', '.join(unsatisfiable_invariants)}"
        )
        self.log(entry)

    def log_immediate_stop(
        self,
        reason: str,
        kernel_state: str,
        triggered_by: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs an immediate stop event.

        Args:
            reason: Why stop was triggered
            kernel_state: State when stop occurred
            triggered_by: What triggered the stop
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.IMMEDIATE_STOP,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},  # Will be populated by context
            resolution_outcome=ResolutionOutcome.STOP,
            context={"triggered_by": triggered_by, **(context or {})},
            message=reason
        )
        self.log(entry)

    def log_ltc_evaluation(
        self,
        source_domain: str,
        target_domain: str,
        logic_framework: str,
        verdict: str,
        reason_codes: list[str],
        failed_invariants: list[str],
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs an LTC (Legitimate Transfer Constraint) evaluation.

        Args:
            source_domain: Domain where logic originates
            target_domain: Domain where logic will be applied
            logic_framework: Description of logic being transferred
            verdict: LTC verdict (ALLOW/DENY/SILENCE)
            reason_codes: Codes explaining verdict
            failed_invariants: Invariants that failed preservation test
            kernel_state: Current kernel state
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.LTC_TRANSFER_EVALUATED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.STOP if verdict == "deny" else ResolutionOutcome.PROCEED,
            context={
                "source_domain": source_domain,
                "target_domain": target_domain,
                "logic_framework": logic_framework,
                "verdict": verdict,
                "reason_codes": reason_codes,
                "failed_invariants": failed_invariants,
                **(context or {})
            },
            message=f"LTC evaluation: {verdict} for transfer from {source_domain} to {target_domain}"
        )
        self.log(entry)

    def get_all_entries(self) -> list[LogEntry]:
        """
        Returns all log entries.

        Returns:
            Immutable copy of all log entries
        """
        return self._entries.copy()

    def get_entries_by_type(self, event_type: EventType) -> list[LogEntry]:
        """
        Retrieves all log entries of a specific type.

        Args:
            event_type: The event type to filter by

        Returns:
            List of matching log entries
        """
        return [e for e in self._entries if e.event_type == event_type]

    def get_violation_count(self) -> int:
        """Returns the count of invariant violations logged."""
        return len(self.get_entries_by_type(EventType.INVARIANT_VIOLATION))

    def has_violations(self) -> bool:
        """Returns True if any invariant violations have been logged."""
        return self.get_violation_count() > 0

    def clear(self) -> None:
        """
        FORBIDDEN: Logs are immutable.

        Raises:
            LogMutationAttempt: Always
        """
        raise LogMutationAttempt("Cannot clear logs - append-only immutable log")

    def delete_entry(self, index: int) -> None:
        """
        FORBIDDEN: Logs are immutable.

        Raises:
            LogMutationAttempt: Always
        """
        raise LogMutationAttempt("Cannot delete log entries - append-only immutable log")


# ============================================================================
# GLOBAL LOGGER INSTANCE
# ============================================================================

# Default in-memory logger for testing/development
_default_logger: Optional[AuditLogger] = None


def get_default_logger() -> AuditLogger:
    """
    Gets the default global audit logger.

    Returns:
        The default AuditLogger instance
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = AuditLogger(in_memory=True)
    return _default_logger


def set_default_logger(logger: AuditLogger) -> None:
    """
    Sets the default global audit logger.

    Args:
        logger: The logger to use as default
    """
    global _default_logger
    _default_logger = logger
