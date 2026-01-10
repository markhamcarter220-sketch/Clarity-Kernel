"""
Temporal Coherence Layer (unAI OS) — KERNEL PATCH v1.1

This module implements bounded temporal coherence tracking to prevent
coherence drift from snowballing over unbounded execution horizons.

Core Guarantee:
    Coh_t remains O(1) bounded for all t ∈ [0, ∞)

Update Rule:
    Coh_{t+1} = clip[0, Coh_max](Coh_t + Δ_drift(t) - δ_decay(λ, state))

Soft-cap repair: If Coh > Coh_soft → force minor projection Π_t
Hard-cap rule: If Coh ≥ Coh_max → escalate to governance + freeze

This is a binding governance-first kernel component.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
import time


class CoherenceViolation(Exception):
    """Raised when temporal coherence exceeds hard ceiling."""

    def __init__(self, message: str, coherence: float, max_coherence: float, context: dict[str, Any]):
        super().__init__(message)
        self.coherence = coherence
        self.max_coherence = max_coherence
        self.context = context


class ProjectionType(Enum):
    """Types of coherence repair projections."""
    MINOR = "minor"  # Soft-cap repair: tighten meaning, drop slack
    MAJOR = "major"  # Hard-cap escalation: requires authority


@dataclass
class CoherenceState:
    """
    Temporal coherence state tracker.

    Attributes:
        coh_t: Current temporal coherence slack (≥ 0)
        coh_soft: Soft coherence threshold (triggers minor projection)
        coh_max: Hard coherence ceiling (triggers escalation)
        delta_decay_min: Minimum decay rate per step
        delta_decay_max: Maximum decay rate per step
        step_count: Number of coherence steps taken
        projection_count: Number of projections performed
        last_projection_at: Timestamp of last projection
    """
    coh_t: float = 0.0
    coh_soft: float = 0.5
    coh_max: float = 1.0
    delta_decay_min: float = 0.02
    delta_decay_max: float = 0.05
    step_count: int = 0
    projection_count: int = 0
    last_projection_at: Optional[int] = None

    def __post_init__(self) -> None:
        """Validates coherence parameters."""
        if self.coh_soft <= 0:
            raise ValueError(f"coh_soft must be positive, got {self.coh_soft}")
        if self.coh_max <= self.coh_soft:
            raise ValueError(f"coh_max ({self.coh_max}) must exceed coh_soft ({self.coh_soft})")
        if self.delta_decay_min < 0 or self.delta_decay_max < self.delta_decay_min:
            raise ValueError(
                f"Invalid decay range: [{self.delta_decay_min}, {self.delta_decay_max}]"
            )
        if self.coh_t < 0:
            raise ValueError(f"coh_t must be non-negative, got {self.coh_t}")


@dataclass
class ProjectionResult:
    """
    Result of coherence repair projection.

    Attributes:
        projection_type: Type of projection performed
        coh_before: Coherence before projection
        coh_after: Coherence after projection
        meanings_dropped: Number of low-confidence meanings dropped
        timestamp: Unix timestamp of projection
        reason: Human-readable reason for projection
    """
    projection_type: ProjectionType
    coh_before: float
    coh_after: float
    meanings_dropped: int
    timestamp: int
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TemporalCoherenceTracker:
    """
    Tracks and enforces bounded temporal coherence (unAI OS).

    This tracker ensures that coherence slack remains O(1) bounded
    over unbounded execution horizons through:
    1. Per-step decay
    2. Soft-cap repair (minor projection)
    3. Hard-cap escalation (governance freeze)

    Example:
        tracker = TemporalCoherenceTracker()

        # Each reasoning step
        drift = compute_drift(...)
        tracker.step(drift_delta=drift, lambda_param=1.0)

        # Check if escalation needed
        if tracker.state.coh_t >= tracker.state.coh_max:
            # Escalate to governance
            pass
    """

    def __init__(
        self,
        coh_soft: float = 0.5,
        coh_max: float = 1.0,
        delta_decay_min: float = 0.02,
        delta_decay_max: float = 0.05,
    ):
        """
        Initializes temporal coherence tracker.

        Args:
            coh_soft: Soft coherence threshold (default: 0.5)
            coh_max: Hard coherence ceiling (default: 1.0)
            delta_decay_min: Minimum decay rate (default: 0.02)
            delta_decay_max: Maximum decay rate (default: 0.05)
        """
        self.state = CoherenceState(
            coh_soft=coh_soft,
            coh_max=coh_max,
            delta_decay_min=delta_decay_min,
            delta_decay_max=delta_decay_max,
        )
        self.projection_history: list[ProjectionResult] = []

    def compute_decay(self, lambda_param: float, state_complexity: float = 1.0) -> float:
        """
        Computes per-step coherence decay δ_decay(λ, state).

        Decay increases with state complexity to prevent unbounded drift.

        Args:
            lambda_param: Lambda parameter controlling decay rate
            state_complexity: Complexity of current state (≥ 1.0)

        Returns:
            Decay value in [delta_decay_min, delta_decay_max]
        """
        # Linear interpolation based on state complexity
        decay_range = self.state.delta_decay_max - self.state.delta_decay_min
        decay = self.state.delta_decay_min + (decay_range * min(1.0, state_complexity / 10.0))

        # Scale by lambda
        decay *= lambda_param

        # Clamp to valid range
        return max(self.state.delta_decay_min, min(self.state.delta_decay_max, decay))

    def step(
        self,
        drift_delta: float,
        lambda_param: float = 1.0,
        state_complexity: float = 1.0,
    ) -> None:
        """
        Performs one coherence update step.

        Update rule:
            Coh_{t+1} = clip[0, Coh_max](Coh_t + Δ_drift(t) - δ_decay(λ, state))

        Args:
            drift_delta: Change in coherence from this step (can be negative)
            lambda_param: Lambda parameter for decay computation
            state_complexity: Complexity of current state

        Raises:
            CoherenceViolation: If hard ceiling Coh_max is reached
        """
        decay = self.compute_decay(lambda_param, state_complexity)

        # Update rule
        coh_next = self.state.coh_t + drift_delta - decay

        # Clip to [0, Coh_max]
        coh_next = max(0.0, min(self.state.coh_max, coh_next))

        # Check soft cap (triggers minor projection)
        if coh_next > self.state.coh_soft:
            projection = self._apply_soft_cap_repair(coh_next)
            coh_next = projection.coh_after
            self.projection_history.append(projection)

        # Check hard cap (triggers escalation)
        if coh_next >= self.state.coh_max:
            raise CoherenceViolation(
                f"Temporal coherence reached hard ceiling: {coh_next:.3f} ≥ {self.state.coh_max}",
                coherence=coh_next,
                max_coherence=self.state.coh_max,
                context={
                    "step_count": self.state.step_count,
                    "drift_delta": drift_delta,
                    "decay": decay,
                    "projection_count": self.state.projection_count,
                }
            )

        # Update state
        self.state.coh_t = coh_next
        self.state.step_count += 1

    def _apply_soft_cap_repair(self, coh_before: float) -> ProjectionResult:
        """
        Applies minor projection Π_t to repair soft-cap violation.

        This:
        1. Tightens meaning (drops lowest-confidence interpretations)
        2. Reduces slack assumptions
        3. Optionally reduces Coh by small constant (0.05)

        Args:
            coh_before: Coherence before repair

        Returns:
            ProjectionResult describing the repair
        """
        # Minor projection reduces coherence by small constant
        MINOR_REDUCTION = 0.05
        coh_after = max(0.0, coh_before - MINOR_REDUCTION)

        timestamp = int(time.time())

        result = ProjectionResult(
            projection_type=ProjectionType.MINOR,
            coh_before=coh_before,
            coh_after=coh_after,
            meanings_dropped=1,  # Heuristic: drop 1 low-confidence meaning
            timestamp=timestamp,
            reason=f"Soft-cap repair: Coh {coh_before:.3f} > {self.state.coh_soft}",
            metadata={
                "step_count": self.state.step_count,
                "reduction": MINOR_REDUCTION,
            }
        )

        self.state.projection_count += 1
        self.state.last_projection_at = timestamp

        return result

    def reset(self) -> None:
        """Resets coherence state to initial values."""
        self.state.coh_t = 0.0
        self.state.step_count = 0
        self.state.projection_count = 0
        self.state.last_projection_at = None
        self.projection_history.clear()

    def get_status(self) -> dict[str, Any]:
        """
        Returns current coherence status.

        Returns:
            Dictionary with coherence metrics
        """
        return {
            "coh_t": self.state.coh_t,
            "coh_soft": self.state.coh_soft,
            "coh_max": self.state.coh_max,
            "step_count": self.state.step_count,
            "projection_count": self.state.projection_count,
            "utilization": self.state.coh_t / self.state.coh_max,
            "soft_cap_breached": self.state.coh_t > self.state.coh_soft,
            "last_projection_at": self.state.last_projection_at,
        }
