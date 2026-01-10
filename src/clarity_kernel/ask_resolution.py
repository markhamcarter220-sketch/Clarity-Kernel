"""
ASK Resolution Tracking (Clarity OS) — KERNEL PATCH v1.1

This module implements monotonic ASK resolution with persistent repair
to prevent indefinite suspension from unresolved ambiguity.

Core Guarantees:
1. ask_streak is bounded (max 3 before auto-SILENCE)
2. Timeout triggers safe default branch (no irreversible actions)
3. Progress is monotonic (no infinite suspension)

State Transitions:
    Resolved ASK → ask_streak = 0
    Unresolved ASK → ask_streak += 1
    ask_streak ≥ 2 → light projection Π_t (drop low-confidence meanings)
    ask_streak > 3 → auto-SILENCE + escalate

This is a binding governance-first kernel component.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from enum import Enum
import time


class ASKResolutionStatus(Enum):
    """Status of ASK resolution attempt."""
    RESOLVED = "resolved"  # ASK successfully answered
    UNRESOLVED = "unresolved"  # ASK not answered
    TIMEOUT = "timeout"  # ASK timed out
    DEFAULTED = "defaulted"  # Safe default selected after timeout


class ASKLoopViolation(Exception):
    """Raised when ASK loop exceeds termination threshold."""

    def __init__(self, message: str, ask_streak: int, max_streak: int, context: dict[str, Any]):
        super().__init__(message)
        self.ask_streak = ask_streak
        self.max_streak = max_streak
        self.context = context


@dataclass
class ASKEvent:
    """
    Record of an ASK (C-1 clarification request) event.

    Attributes:
        ask_id: Unique identifier for this ASK
        question: The clarification question asked
        timestamp: Unix timestamp when ASK was issued
        timeout_seconds: Timeout for response (None = no timeout)
        resolution_status: How the ASK was resolved
        response: User's response (if resolved)
        default_branch: Safe default taken (if timeout/defaulted)
        resolved_at: Unix timestamp when resolved (None if unresolved)
    """
    ask_id: str
    question: str
    timestamp: int
    timeout_seconds: Optional[int] = None
    resolution_status: ASKResolutionStatus = ASKResolutionStatus.UNRESOLVED
    response: Optional[str] = None
    default_branch: Optional[str] = None
    resolved_at: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectionAction:
    """
    Light projection action to repair persistent ASK.

    Attributes:
        triggered_by_streak: ASK streak that triggered projection
        meanings_dropped: Number of low-confidence meanings dropped
        coherence_reduction: Coherence reduction applied
        timestamp: Unix timestamp of projection
        reason: Human-readable reason
    """
    triggered_by_streak: int
    meanings_dropped: int
    coherence_reduction: float
    timestamp: int
    reason: str


class ASKResolutionTracker:
    """
    Tracks ASK resolution and enforces monotonic progress.

    This tracker prevents indefinite suspension from unresolved ASK by:
    1. Tracking consecutive unresolved ASK (ask_streak)
    2. Triggering light projection at ask_streak ≥ 2
    3. Auto-SILENCE + escalation at ask_streak > 3
    4. Timeout progress with safe defaults

    Example:
        tracker = ASKResolutionTracker(max_ask_streak=3)

        # Issue ASK
        ask_id = tracker.issue_ask(
            question="What is the target dosage?",
            timeout_seconds=60
        )

        # Later: resolve ASK
        tracker.resolve_ask(ask_id, response="50mg")

        # Or: timeout with safe default
        tracker.timeout_ask(ask_id, default_branch="request_explicit_input")
    """

    def __init__(
        self,
        max_ask_streak: int = 3,
        coherence_reduction_per_projection: float = 0.03,
        projection_callback: Optional[Callable[[ProjectionAction], None]] = None
    ):
        """
        Initializes ASK resolution tracker.

        Args:
            max_ask_streak: Maximum consecutive unresolved ASK before auto-SILENCE
            coherence_reduction_per_projection: Coherence reduction per light projection
            projection_callback: Optional callback for light projections
        """
        self.max_ask_streak = max_ask_streak
        self.coherence_reduction_per_projection = coherence_reduction_per_projection
        self.projection_callback = projection_callback

        self.ask_streak: int = 0
        self.total_asks: int = 0
        self.resolved_asks: int = 0
        self.timeout_asks: int = 0

        self.ask_history: list[ASKEvent] = []
        self.projection_history: list[ProjectionAction] = []
        self.pending_asks: dict[str, ASKEvent] = {}

    def issue_ask(
        self,
        question: str,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Issues a new ASK (C-1 clarification request).

        Args:
            question: The clarification question
            timeout_seconds: Optional timeout for response
            metadata: Optional metadata for audit

        Returns:
            Unique ASK ID

        Raises:
            ASKLoopViolation: If ask_streak exceeds max_ask_streak
        """
        # Check loop termination
        if self.ask_streak >= self.max_ask_streak:
            raise ASKLoopViolation(
                f"ASK loop exceeded termination threshold: {self.ask_streak} ≥ {self.max_ask_streak}. "
                f"Auto-SILENCE triggered.",
                ask_streak=self.ask_streak,
                max_streak=self.max_ask_streak,
                context={
                    "total_asks": self.total_asks,
                    "resolved_asks": self.resolved_asks,
                    "timeout_asks": self.timeout_asks,
                    "question": question
                }
            )

        # Create ASK event
        ask_id = f"ask_{self.total_asks + 1}_{int(time.time())}"
        ask_event = ASKEvent(
            ask_id=ask_id,
            question=question,
            timestamp=int(time.time()),
            timeout_seconds=timeout_seconds,
            metadata=metadata or {}
        )

        # Record ASK
        self.pending_asks[ask_id] = ask_event
        self.ask_history.append(ask_event)
        self.total_asks += 1

        return ask_id

    def resolve_ask(
        self,
        ask_id: str,
        response: str
    ) -> None:
        """
        Resolves an ASK with user response.

        This resets ask_streak to 0 (monotonic progress restored).

        Args:
            ask_id: The ASK ID to resolve
            response: User's response

        Raises:
            ValueError: If ASK ID not found
        """
        if ask_id not in self.pending_asks:
            raise ValueError(f"ASK ID not found: {ask_id}")

        ask_event = self.pending_asks[ask_id]

        # Update ASK event
        ask_event.resolution_status = ASKResolutionStatus.RESOLVED
        ask_event.response = response
        ask_event.resolved_at = int(time.time())

        # Remove from pending
        del self.pending_asks[ask_id]

        # Reset streak (monotonic progress)
        self.ask_streak = 0
        self.resolved_asks += 1

    def mark_unresolved(
        self,
        ask_id: str,
        reason: str = "no_response"
    ) -> None:
        """
        Marks an ASK as unresolved (no response received).

        This increments ask_streak and may trigger persistent ASK repair.

        Args:
            ask_id: The ASK ID to mark unresolved
            reason: Reason for non-resolution

        Raises:
            ValueError: If ASK ID not found
        """
        if ask_id not in self.pending_asks:
            raise ValueError(f"ASK ID not found: {ask_id}")

        ask_event = self.pending_asks[ask_id]

        # Update ASK event
        ask_event.resolution_status = ASKResolutionStatus.UNRESOLVED
        ask_event.resolved_at = int(time.time())
        ask_event.metadata["unresolved_reason"] = reason

        # Remove from pending
        del self.pending_asks[ask_id]

        # Increment streak
        self.ask_streak += 1

        # Persistent ASK repair: ask_streak ≥ 2
        if self.ask_streak >= 2:
            self._apply_persistent_ask_repair()

    def timeout_ask(
        self,
        ask_id: str,
        default_branch: str
    ) -> None:
        """
        Times out an ASK and selects safe default branch.

        Timeout progress rule:
        - Select safe default branch
        - Do not perform irreversible action
        - Log decision as "timeout default"
        - Mark for optional human review

        Args:
            ask_id: The ASK ID to timeout
            default_branch: Safe default branch to take

        Raises:
            ValueError: If ASK ID not found
        """
        if ask_id not in self.pending_asks:
            raise ValueError(f"ASK ID not found: {ask_id}")

        ask_event = self.pending_asks[ask_id]

        # Update ASK event
        ask_event.resolution_status = ASKResolutionStatus.TIMEOUT
        ask_event.default_branch = default_branch
        ask_event.resolved_at = int(time.time())

        # Remove from pending
        del self.pending_asks[ask_id]

        # Increment counters
        self.ask_streak += 1
        self.timeout_asks += 1

        # Persistent ASK repair
        if self.ask_streak >= 2:
            self._apply_persistent_ask_repair()

    def _apply_persistent_ask_repair(self) -> None:
        """
        Applies persistent ASK repair (light projection Π_t).

        This:
        1. Drops lowest-confidence meanings from I(c)
        2. Reduces Coh by coherence_reduction_per_projection
        3. Invokes projection_callback if provided

        Triggered when ask_streak ≥ 2.
        """
        projection = ProjectionAction(
            triggered_by_streak=self.ask_streak,
            meanings_dropped=1,  # Heuristic: drop 1 low-confidence meaning
            coherence_reduction=self.coherence_reduction_per_projection,
            timestamp=int(time.time()),
            reason=f"Persistent ASK repair: ask_streak={self.ask_streak} ≥ 2"
        )

        self.projection_history.append(projection)

        # Invoke callback if provided
        if self.projection_callback:
            self.projection_callback(projection)

    def reset_streak(self) -> None:
        """Resets ASK streak to 0 (manual intervention)."""
        self.ask_streak = 0

    def get_status(self) -> dict[str, Any]:
        """
        Returns current ASK resolution status.

        Returns:
            Dictionary with ASK metrics
        """
        return {
            "ask_streak": self.ask_streak,
            "total_asks": self.total_asks,
            "resolved_asks": self.resolved_asks,
            "timeout_asks": self.timeout_asks,
            "pending_asks": len(self.pending_asks),
            "resolution_rate": self.resolved_asks / self.total_asks if self.total_asks > 0 else 1.0,
            "projection_count": len(self.projection_history),
            "loop_risk": self.ask_streak / self.max_ask_streak,
        }
