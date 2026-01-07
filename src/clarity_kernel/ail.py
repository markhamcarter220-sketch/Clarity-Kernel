"""
AIL — Adaptive Interaction Layer (Non-Normative)

This module provides an optional wrapper around the Clarity Kernel SSL
for managing interactive clarification without modifying SSL behavior.

IMPORTANT:
- AIL is NOT part of the canonical SSL
- SSL remains the authoritative decision layer
- AIL provides UX conveniences only
- All invariants and STOP semantics remain unchanged
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .ssl import ClarityKernel, PermissionRequest, PermissionResponse, PermissionDenied
from .invariants import ClarityInvariantViolation


# ============================================================================
# RESPONSE TYPES
# ============================================================================


class AILResponseType(Enum):
    """Types of responses AIL can return."""
    PASSTHROUGH = "passthrough"  # SSL decision unchanged
    CLARIFY = "clarify"          # Requesting clarification
    TAD = "tad"                  # Terminal Ambiguity Declaration
    SILENCE = "silence"          # No output


@dataclass
class AILResponse:
    """
    Response from AIL wrapper.

    Attributes:
        response_type: Type of AIL response
        ssl_response: Original SSL response (if passthrough)
        message: Message to return (empty for silence)
        context: Additional context data
    """
    response_type: AILResponseType
    ssl_response: Optional[PermissionResponse] = None
    message: str = ""
    context: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.context is None:
            self.context = {}


# ============================================================================
# AIL SESSION STATE
# ============================================================================


class AILSession:
    """
    Manages state for a single AIL interaction session.

    Tracks clarification attempts and terminal ambiguity state.
    This is NOT part of SSL - it's interaction-layer bookkeeping.
    """

    def __init__(self, max_clarifications: int = 2):
        """
        Initialize AIL session.

        Args:
            max_clarifications: Maximum clarification attempts before TAD
        """
        self.max_clarifications = max_clarifications
        self.clarification_attempts = 0
        self.terminal_declared = False
        self.last_ambiguity_fingerprint: Optional[str] = None

    def request_clarification(self, fingerprint: str) -> bool:
        """
        Determines if clarification should be requested.

        Args:
            fingerprint: Hash of current input

        Returns:
            True if clarification should be requested, False otherwise
        """
        # If terminal already declared, no more clarifications
        if self.terminal_declared:
            return False

        # If same input as last time, we're looping
        if self.last_ambiguity_fingerprint == fingerprint:
            # Already tried clarifying this exact input
            return False

        # Within budget, can clarify
        if self.clarification_attempts < self.max_clarifications:
            self.last_ambiguity_fingerprint = fingerprint
            self.clarification_attempts += 1
            return True

        # Budget exhausted - declare terminal ambiguity
        self.terminal_declared = True
        return False

    def reset(self) -> None:
        """Resets session state (when ambiguity is resolved)."""
        self.clarification_attempts = 0
        self.terminal_declared = False
        self.last_ambiguity_fingerprint = None

    def is_terminal(self) -> bool:
        """Returns True if terminal ambiguity has been declared."""
        return self.terminal_declared


# ============================================================================
# AIL WRAPPER
# ============================================================================


class AILWrapper:
    """
    Wrapper around Clarity Kernel SSL for interactive clarification.

    This wrapper does NOT modify SSL behavior. It only interprets
    SSL STOP decisions and manages interaction state.
    """

    def __init__(self, kernel: ClarityKernel, session: Optional[AILSession] = None):
        """
        Initialize AIL wrapper.

        Args:
            kernel: The Clarity Kernel SSL instance
            session: AIL session for state tracking (creates new if None)
        """
        self.kernel = kernel
        self.session = session or AILSession()

    def step(self, request: PermissionRequest) -> AILResponse:
        """
        Process a permission request through AIL/SSL pipeline.

        Args:
            request: The permission request to evaluate

        Returns:
            AILResponse with decision and any clarification needed
        """
        # Compute fingerprint of this request
        fingerprint = self._compute_fingerprint(request)

        # Check if this is new input (different from last ambiguity)
        if self.session.last_ambiguity_fingerprint is not None:
            if fingerprint != self.session.last_ambiguity_fingerprint:
                # New input - reset session
                self.session.reset()

        try:
            # Call SSL kernel
            response = self.kernel.request_permission(request)

            # SSL allowed - passthrough
            # If we get here, ambiguity was resolved
            if self.session.clarification_attempts > 0:
                self.session.reset()

            return AILResponse(
                response_type=AILResponseType.PASSTHROUGH,
                ssl_response=response,
                message="",
                context={"granted": response.granted}
            )

        except PermissionDenied as e:
            # SSL denied - check if it's ambiguity
            is_ambiguity = self._is_ambiguity_stop(e)

            if is_ambiguity:
                return self._handle_ambiguity(fingerprint, e)
            else:
                # Non-ambiguity stop - passthrough unchanged
                return AILResponse(
                    response_type=AILResponseType.PASSTHROUGH,
                    ssl_response=None,
                    message=str(e),
                    context={
                        "kernel_state": e.kernel_state,
                        "reason": e.reason
                    }
                )

    def _handle_ambiguity(self, fingerprint: str, exception: PermissionDenied) -> AILResponse:
        """
        Handle ambiguity stop from SSL.

        Args:
            fingerprint: Input fingerprint
            exception: The PermissionDenied exception from SSL

        Returns:
            Appropriate AIL response (CLARIFY, TAD, or SILENCE)
        """
        # Check if in terminal state with same input
        if self.session.is_terminal():
            if fingerprint == self.session.last_ambiguity_fingerprint:
                # Same ambiguous input after TAD - silence
                return AILResponse(
                    response_type=AILResponseType.SILENCE,
                    message="",
                    context={"reason": "terminal_ambiguity_persists"}
                )

        # Check if we should request clarification
        if self.session.request_clarification(fingerprint):
            # Within budget - request clarification
            return AILResponse(
                response_type=AILResponseType.CLARIFY,
                message=self._get_clarification_message(exception),
                context={
                    "attempts": self.session.clarification_attempts,
                    "budget": self.session.max_clarifications
                }
            )

        # Budget exhausted - terminal ambiguity declaration
        return AILResponse(
            response_type=AILResponseType.TAD,
            message=self._get_tad_message(),
            context={
                "attempts": self.session.clarification_attempts,
                "terminal": True
            }
        )

    @staticmethod
    def _is_ambiguity_stop(exception: PermissionDenied) -> bool:
        """
        Determines if a PermissionDenied is due to ambiguity (I-1 violation).

        Args:
            exception: The PermissionDenied exception

        Returns:
            True if this is an ambiguity stop (I-1 violation)
        """
        # Check if the reason indicates clarity invariant violation
        reason_lower = exception.reason.lower()
        return (
            "clarity" in reason_lower or
            "ambiguous" in reason_lower or
            "i-1" in reason_lower
        )

    @staticmethod
    def _compute_fingerprint(request: PermissionRequest) -> str:
        """
        Computes deterministic fingerprint of a permission request.

        Args:
            request: The permission request

        Returns:
            SHA256 hash of request's structural content
        """
        # Build canonical representation
        content = {
            "operation_id": request.operation_id,
            "definitions": sorted(request.required_definitions.items()),
            "thresholds": sorted(request.required_thresholds.items()),
            "constraints": sorted(request.required_constraints),
            "variables": sorted([
                (v.name, v.resolved, v.material)
                for v in request.variables
            ])
        }

        # Compute hash
        content_json = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_json.encode()).hexdigest()

    @staticmethod
    def _get_clarification_message(exception: PermissionDenied) -> str:
        """
        Generates neutral clarification request message.

        Args:
            exception: The ambiguity exception from SSL

        Returns:
            Clarification request message
        """
        return "To proceed without assumptions, provide the missing definitions/variables required by the request."

    @staticmethod
    def _get_tad_message() -> str:
        """
        Returns canonical Terminal Ambiguity Declaration message.

        Returns:
            TAD message (exact as specified)
        """
        return (
            "The question remains ambiguous in a way that does not admit a determinate answer "
            "without introducing assumptions. Under the Clarity Kernel, further resolution is not "
            "possible without violating inference constraints."
        )
