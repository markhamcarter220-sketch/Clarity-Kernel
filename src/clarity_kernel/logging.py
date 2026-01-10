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
import hashlib


# ============================================================================
# CONSTANTS
# ============================================================================

SSL_VERSION = "v1.2.0"  # Must match SPECIFICATION.md


# ============================================================================
# ENUMS
# ============================================================================


class EventType(Enum):
    """
    Types of events that must be logged.

    KERNEL PATCH v1.1 - Ledger Totality:
    All cannon fires (ASK, SILENCE, projection, escalation, rollback) MUST be logged.
    """
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

    # KERNEL PATCH v1.1 - Cannon Fire Events (Ledger Totality)
    ASK_ISSUED = "ask_issued"  # C-1 clarification request
    ASK_RESOLVED = "ask_resolved"  # ASK answered by user
    ASK_UNRESOLVED = "ask_unresolved"  # ASK not answered
    ASK_TIMEOUT = "ask_timeout"  # ASK timed out, safe default taken
    SILENCE = "silence"  # I-6 silence enforced (guessing forbidden)
    PROJECTION = "projection"  # Π_t coherence repair projection
    ROLLBACK = "rollback"  # State rollback to k* prefix
    EJECT = "eject"  # Execution ejection
    COHERENCE_VIOLATION = "coherence_violation"  # Temporal coherence hard cap
    ASK_LOOP_TERMINATED = "ask_loop_terminated"  # Auto-SILENCE from ASK loop


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


class ChainIntegrityViolation(Exception):
    """
    Raised when hash chain verification fails.

    This indicates log tampering or corruption.
    """

    def __init__(self, message: str, failed_at_index: int, expected_hash: str, actual_hash: str):
        super().__init__(message)
        self.failed_at_index = failed_at_index
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class LogEntry:
    """
    Immutable audit log entry with tamper-evident hash chain.

    Contains all required fields per Section 13, plus cryptographic hash chain
    for tamper detection.

    Hash Chain Structure:
    - event_id: Sequential counter (0, 1, 2, ...)
    - prev_hash: SHA-256 hash of previous record (NULL for genesis)
    - payload_hash: SHA-256 hash of this record's payload
    - record_hash: SHA-256(prev_hash || payload_hash)

    Any modification to historical records breaks the chain and is
    mechanically detectable via verify_chain().
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

    # Hash chain fields (added for tamper-evidence)
    event_id: int = 0
    prev_hash: str = "NULL"  # SHA-256 hash of previous record, or "NULL" for genesis
    payload_hash: str = ""   # SHA-256 hash of this record's payload
    record_hash: str = ""    # SHA-256(prev_hash || payload_hash)

    def to_dict(self) -> dict[str, Any]:
        """Converts log entry to dictionary for serialization."""
        return {
            # Core fields
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
            "message": self.message,
            # Hash chain fields
            "event_id": self.event_id,
            "prev_hash": self.prev_hash,
            "payload_hash": self.payload_hash,
            "record_hash": self.record_hash
        }

    def compute_payload_hash(self) -> str:
        """
        Computes SHA-256 hash of this record's payload.

        The payload includes all fields EXCEPT the hash chain fields themselves.
        This ensures the hash represents the actual event data.

        Returns:
            Hex-encoded SHA-256 hash
        """
        payload = {
            "event_id": self.event_id,
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
        # Canonical JSON serialization (sorted keys for determinism)
        payload_json = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()

    @staticmethod
    def compute_record_hash(prev_hash: str, payload_hash: str) -> str:
        """
        Computes the record hash from previous hash and payload hash.

        record_hash = SHA-256(prev_hash || payload_hash)

        Args:
            prev_hash: Hash of previous record (or "NULL" for genesis)
            payload_hash: Hash of current record's payload

        Returns:
            Hex-encoded SHA-256 hash
        """
        combined = f"{prev_hash}{payload_hash}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def to_json(self) -> str:
        """Converts log entry to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# ============================================================================
# AUDIT LOGGER
# ============================================================================


class AuditLogger:
    """
    Immutable, append-only audit logger with tamper-evident hash chain.

    CRITICAL PROPERTIES:
    - Logs are never deleted or modified
    - All events are captured
    - No silent suppression
    - Violations of logging invariant raise exceptions
    - Hash chain mechanically proves immutability

    HASH CHAIN STRUCTURE:
    Each record contains:
    - event_id: Sequential counter (0, 1, 2, ...)
    - prev_hash: SHA-256 hash of previous record
    - payload_hash: SHA-256 hash of this record's payload
    - record_hash: SHA-256(prev_hash || payload_hash)

    Any modification to historical records breaks the chain and is
    detectable via verify_chain().
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

        # Hash chain state
        self._next_event_id: int = 0
        self._last_record_hash: str = "NULL"  # Genesis record has prev_hash = NULL

        # Create log file if specified
        if self._log_file:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self._log_file.exists():
                self._log_file.touch()

    def log(self, entry: LogEntry) -> None:
        """
        Appends an immutable log entry with tamper-evident hash chain.

        This method:
        1. Assigns event_id (sequential counter)
        2. Sets prev_hash to last record's hash
        3. Computes payload_hash from entry data
        4. Computes record_hash = SHA-256(prev_hash || payload_hash)
        5. Appends the hash-chained entry

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

        # Import dataclasses.replace for creating modified frozen instance
        from dataclasses import replace

        # Build hash-chained entry
        chained_entry = replace(
            entry,
            event_id=self._next_event_id,
            prev_hash=self._last_record_hash
        )

        # Compute payload hash (based on event data)
        payload_hash = chained_entry.compute_payload_hash()

        # Compute record hash (chaining to previous record)
        record_hash = LogEntry.compute_record_hash(
            chained_entry.prev_hash,
            payload_hash
        )

        # Create final entry with all hashes
        final_entry = replace(
            chained_entry,
            payload_hash=payload_hash,
            record_hash=record_hash
        )

        # Update chain state for next record
        self._next_event_id += 1
        self._last_record_hash = record_hash

        # Append to in-memory log
        if self._in_memory:
            self._entries.append(final_entry)

        # Append to file log
        if self._log_file:
            try:
                with open(self._log_file, 'a') as f:
                    f.write(final_entry.to_json() + '\n')
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

    # ========================================================================
    # KERNEL PATCH v1.1 - Cannon Fire Logging (Ledger Totality)
    # ========================================================================

    def log_ask_issued(
        self,
        ask_id: str,
        question: str,
        kernel_state: str,
        timeout_seconds: Optional[int] = None,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs an ASK (C-1 clarification request) cannon fire.

        KERNEL PATCH v1.1 - Ledger Totality:
        Every cannon fire MUST be logged with full context.

        Args:
            ask_id: Unique ASK identifier
            question: The clarification question
            kernel_state: Current kernel state
            timeout_seconds: Optional timeout
            context: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ASK_ISSUED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.ESCALATE,
            context={
                "ask_id": ask_id,
                "question": question,
                "timeout_seconds": timeout_seconds,
                "triggering_rule": "C-1",
                **(context or {})
            },
            message=f"ASK issued: {question}"
        )
        self.log(entry)

    def log_ask_resolved(
        self,
        ask_id: str,
        question: str,
        response: str,
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs ASK resolution (user provided answer)."""
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ASK_RESOLVED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.PROCEED,
            context={
                "ask_id": ask_id,
                "question": question,
                "response": response,
                "resolution_status": "resolved",
                **(context or {})
            },
            message=f"ASK resolved: {ask_id}"
        )
        self.log(entry)

    def log_ask_unresolved(
        self,
        ask_id: str,
        question: str,
        kernel_state: str,
        reason: str = "no_response",
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs ASK unresolved (no response received)."""
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ASK_UNRESOLVED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.STOP,
            context={
                "ask_id": ask_id,
                "question": question,
                "reason": reason,
                "resolution_status": "unresolved",
                **(context or {})
            },
            message=f"ASK unresolved: {ask_id} ({reason})"
        )
        self.log(entry)

    def log_ask_timeout(
        self,
        ask_id: str,
        question: str,
        default_branch: str,
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs ASK timeout with safe default branch."""
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ASK_TIMEOUT,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.PROCEED,
            context={
                "ask_id": ask_id,
                "question": question,
                "default_branch": default_branch,
                "resolution_status": "timeout",
                "irreversible_action": False,  # Timeout never performs irreversible action
                **(context or {})
            },
            message=f"ASK timeout: {ask_id}, taking safe default: {default_branch}"
        )
        self.log(entry)

    def log_silence(
        self,
        variable_name: str,
        kernel_state: str,
        reason: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs SILENCE cannon fire (I-6 enforcement).

        SILENCE is valid output when guessing is forbidden.
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.SILENCE,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={"I-6": True},  # Silence upholds I-6
            resolution_outcome=ResolutionOutcome.STOP,
            context={
                "variable_name": variable_name,
                "reason": reason,
                "triggering_rule": "I-6",
                **(context or {})
            },
            message=f"SILENCE: guessing forbidden for {variable_name}"
        )
        self.log(entry)

    def log_projection(
        self,
        projection_type: str,
        coh_before: float,
        coh_after: float,
        meanings_dropped: int,
        kernel_state: str,
        reason: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs coherence repair projection Π_t.

        KERNEL PATCH v1.1: Projections must be auditable.
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.PROJECTION,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.PROCEED,
            context={
                "projection_type": projection_type,
                "coh_before": coh_before,
                "coh_after": coh_after,
                "meanings_dropped": meanings_dropped,
                "reason": reason,
                **(context or {})
            },
            message=f"Projection ({projection_type}): Coh {coh_before:.3f} → {coh_after:.3f}"
        )
        self.log(entry)

    def log_rollback(
        self,
        rollback_to_event_id: int,
        rollback_depth: int,
        kernel_state: str,
        reason: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Logs state rollback to k* verified prefix.

        KERNEL PATCH v1.1: Rollback depth = max(0, k* - 2)
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ROLLBACK,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.STOP,
            context={
                "rollback_to_event_id": rollback_to_event_id,
                "rollback_depth": rollback_depth,
                "reason": reason,
                **(context or {})
            },
            message=f"Rollback: depth={rollback_depth} to event_id={rollback_to_event_id}"
        )
        self.log(entry)

    def log_coherence_violation(
        self,
        coherence: float,
        max_coherence: float,
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs temporal coherence hard cap violation."""
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.COHERENCE_VIOLATION,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.ESCALATE,
            context={
                "coherence": coherence,
                "max_coherence": max_coherence,
                "triggering_rule": "unAI_OS_hard_cap",
                **(context or {})
            },
            message=f"Coherence hard cap violated: {coherence:.3f} ≥ {max_coherence}"
        )
        self.log(entry)

    def log_ask_loop_terminated(
        self,
        ask_streak: int,
        max_streak: int,
        kernel_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs auto-SILENCE from ASK loop termination."""
        entry = LogEntry(
            timestamp=datetime.now(),
            event_type=EventType.ASK_LOOP_TERMINATED,
            kernel_state=kernel_state,
            ssl_version=SSL_VERSION,
            invariants_evaluated={},
            resolution_outcome=ResolutionOutcome.ESCALATE,
            context={
                "ask_streak": ask_streak,
                "max_streak": max_streak,
                "action": "auto_silence",
                "triggering_rule": "loop_termination",
                **(context or {})
            },
            message=f"ASK loop terminated: streak={ask_streak} ≥ {max_streak}, auto-SILENCE"
        )
        self.log(entry)

    # ========================================================================
    # End Cannon Fire Logging
    # ========================================================================

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

    def verify_chain(self) -> bool:
        """
        Verifies the integrity of the hash chain.

        This method proves that no records have been tampered with by:
        1. Verifying each record's payload_hash matches its data
        2. Verifying each record's record_hash = SHA-256(prev_hash || payload_hash)
        3. Verifying the chain links correctly (record[i].prev_hash == record[i-1].record_hash)

        Returns:
            True if chain is valid

        Raises:
            ChainIntegrityViolation: If tampering is detected
        """
        if len(self._entries) == 0:
            return True  # Empty chain is valid

        # Verify genesis record
        genesis = self._entries[0]
        if genesis.event_id != 0:
            raise ChainIntegrityViolation(
                f"Genesis record has invalid event_id: {genesis.event_id} (expected 0)",
                failed_at_index=0,
                expected_hash="event_id=0",
                actual_hash=f"event_id={genesis.event_id}"
            )

        if genesis.prev_hash != "NULL":
            raise ChainIntegrityViolation(
                f"Genesis record has invalid prev_hash: {genesis.prev_hash} (expected NULL)",
                failed_at_index=0,
                expected_hash="NULL",
                actual_hash=genesis.prev_hash
            )

        # Verify each record
        for i, entry in enumerate(self._entries):
            # Verify event_id is sequential
            if entry.event_id != i:
                raise ChainIntegrityViolation(
                    f"Record {i} has invalid event_id: {entry.event_id} (expected {i})",
                    failed_at_index=i,
                    expected_hash=f"event_id={i}",
                    actual_hash=f"event_id={entry.event_id}"
                )

            # Verify payload_hash matches computed hash
            computed_payload_hash = entry.compute_payload_hash()
            if entry.payload_hash != computed_payload_hash:
                raise ChainIntegrityViolation(
                    f"Record {i} payload tampering detected: payload_hash mismatch",
                    failed_at_index=i,
                    expected_hash=computed_payload_hash,
                    actual_hash=entry.payload_hash
                )

            # Verify record_hash = SHA-256(prev_hash || payload_hash)
            computed_record_hash = LogEntry.compute_record_hash(
                entry.prev_hash,
                entry.payload_hash
            )
            if entry.record_hash != computed_record_hash:
                raise ChainIntegrityViolation(
                    f"Record {i} hash chain broken: record_hash mismatch",
                    failed_at_index=i,
                    expected_hash=computed_record_hash,
                    actual_hash=entry.record_hash
                )

            # Verify chain links correctly (except for genesis)
            if i > 0:
                prev_entry = self._entries[i - 1]
                if entry.prev_hash != prev_entry.record_hash:
                    raise ChainIntegrityViolation(
                        f"Record {i} chain link broken: prev_hash does not match previous record_hash",
                        failed_at_index=i,
                        expected_hash=prev_entry.record_hash,
                        actual_hash=entry.prev_hash
                    )

        return True


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
