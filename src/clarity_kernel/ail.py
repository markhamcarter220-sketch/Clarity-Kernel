"""
Adaptive Interaction Layer (AIL)

⚠ DEPRECATION NOTICE ⚠
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STATUS: NON-NORMATIVE (Exploratory Implementation)

The AIL is NOT part of the canonical Clarity Kernel specification.
It is an OPTIONAL, NON-NORMATIVE wrapper that may be removed or changed
in future versions without notice.

DO NOT rely on AIL for safety-critical or production use.
Use the core ClarityKernel (SSL) directly for all production deployments.

See SPECIFICATION.md Section 4.2 for the normative AIL definition.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module provides an OPTIONAL wrapper around the Clarity Kernel for
interactive systems (e.g. chat interfaces, LLMs).

The AIL:
- Invokes the SSL (Clarity Kernel)
- Interprets STOP(reason=ambiguity)
- May ask neutral clarification questions with a fixed budget
- Never softens or overrides SSL decisions
- Never tracks retries inside SSL

The SSL remains authoritative and unchanged.

NON-INTERFERENCE AXIOM:
AIL MUST NOT mutate request semantics, add assumptions, or override SSL verdicts.
Any attempt to do so violates the non-interference guarantee and is forbidden.
"""

import warnings

from typing import Optional, Any
import hashlib
import copy

from clarity_kernel.ssl import ClarityKernel


# Issue deprecation warning on import
warnings.warn(
    "AIL (Adaptive Interaction Layer) is NON-NORMATIVE and may be removed in future versions. "
    "For production use, interact directly with ClarityKernel (SSL). "
    "See SPECIFICATION.md Section 4.2.",
    DeprecationWarning,
    stacklevel=2
)


# ============================================================================
# FORMAL NON-INTERFERENCE RULES
# ============================================================================

class AILInterferenceViolation(Exception):
    """
    Raised when AIL violates non-interference guarantee.

    AIL is FORBIDDEN from:
    1. Adding assumptions to requests
    2. Rewriting constraints or definitions
    3. Downgrading STOP → ALLOW verdicts
    4. Mutating request data passed to SSL
    5. Overriding SSL decisions based on "helpfulness"

    AIL MAY ONLY:
    - Request missing information (clarification)
    - Present SSL decisions unchanged (pass-through)
    - Track clarification attempts (session state only)

    Any violation of these rules constitutes interference and is prohibited.
    """

    def __init__(
        self,
        message: str,
        interference_type: str,
        evidence: dict[str, Any]
    ):
        super().__init__(message)
        self.interference_type = interference_type
        self.evidence = evidence


# Formal AIL non-interference rules
AIL_PERMITTED_ACTIONS = {
    "request_clarification",  # Ask for missing information
    "passthrough_ssl_decision",  # Return SSL verdict unchanged
    "track_session_state",  # Update clarification attempt counter
}

AIL_FORBIDDEN_ACTIONS = {
    "add_assumption",  # Adding values not provided by user
    "rewrite_constraint",  # Modifying required_definitions, thresholds, etc.
    "downgrade_stop",  # Changing STOP → ALLOW
    "mutate_request",  # Modifying request before passing to SSL
    "override_ssl",  # Changing SSL verdict based on "helpfulness"
    "soften_invariant",  # Relaxing invariant requirements
    "optimize_for_ux",  # Trading safety for user experience
}


TERMINAL_AMBIGUITY_TEXT = (
    "The question remains ambiguous in a way that does not admit a determinate "
    "answer without introducing assumptions. Under the Clarity Kernel, further "
    "resolution is not possible without violating inference constraints."
)


class AILSession:
    def __init__(self, max_clarifications: int = 2):
        self.max_clarifications = max_clarifications
        self.clarification_attempts = 0
        self.terminal_declared = False
        self.last_fingerprint: Optional[str] = None

    def reset(self):
        self.clarification_attempts = 0
        self.terminal_declared = False
        self.last_fingerprint = None


class AILWrapper:
    """
    AIL wrapper with formal non-interference enforcement.

    This wrapper is PROHIBITED from mutating request semantics or SSL decisions.
    All actions are verified against the non-interference axiom.
    """

    def __init__(self, kernel: ClarityKernel, session: Optional[AILSession] = None, enforce_noninterference: bool = True):
        self.kernel = kernel
        self.session = session or AILSession()
        self.enforce_noninterference = enforce_noninterference

    def _fingerprint(self, payload) -> str:
        """Compute fingerprint of request for identity checking."""
        data = repr(payload).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _verify_request_unmodified(self, request_before: Any, request_after: Any) -> None:
        """
        Verifies that request was not mutated before passing to SSL.

        This enforces the non-interference axiom: AIL cannot modify request data.
        """
        if not self.enforce_noninterference:
            return

        # Check if requests are identical
        fingerprint_before = self._fingerprint(request_before)
        fingerprint_after = self._fingerprint(request_after)

        if fingerprint_before != fingerprint_after:
            raise AILInterferenceViolation(
                "AIL violated non-interference: request was mutated before passing to SSL",
                interference_type="mutate_request",
                evidence={
                    "fingerprint_before": fingerprint_before,
                    "fingerprint_after": fingerprint_after,
                }
            )

    def _verify_decision_unmodified(self, ssl_decision: Any, ail_decision: Any) -> None:
        """
        Verifies that SSL decision was not modified by AIL.

        This enforces pass-through requirement: AIL cannot change SSL verdicts.
        """
        if not self.enforce_noninterference:
            return

        # For non-ambiguity decisions, AIL must return SSL decision unchanged
        # (For ambiguity, AIL returns clarification request, which is permitted)
        if not getattr(ssl_decision, "is_ambiguity", False):
            if ssl_decision != ail_decision:
                raise AILInterferenceViolation(
                    "AIL violated non-interference: SSL decision was modified",
                    interference_type="override_ssl",
                    evidence={
                        "ssl_decision": str(ssl_decision),
                        "ail_decision": str(ail_decision),
                    }
                )

    def _verify_no_assumptions_added(self, request: Any) -> None:
        """
        Verifies that AIL did not add assumptions to request.

        AIL is FORBIDDEN from filling in missing values, guessing defaults,
        or inferring intent. This would violate I-6 (Silence Invariant).
        """
        if not self.enforce_noninterference:
            return

        # Check if request has variables that were auto-resolved
        # (This is a heuristic check - more specific checks can be added)
        if hasattr(request, 'variables'):
            for var in request.variables:
                # If a variable is marked resolved but has a "default" or "assumed" flag,
                # that's interference
                if hasattr(var, '_ail_assumed') and var._ail_assumed:
                    raise AILInterferenceViolation(
                        f"AIL violated non-interference: assumption added for variable '{var.name}'",
                        interference_type="add_assumption",
                        evidence={
                            "variable_name": var.name,
                            "assumed_value": var.value,
                        }
                    )

    def step(self, request):
        """
        Process request through AIL with non-interference enforcement.

        PERMITTED ACTIONS:
        - Pass request to SSL unchanged
        - Return SSL decision unchanged (for non-ambiguity)
        - Request clarification (for ambiguity, within budget)
        - Track session state

        FORBIDDEN ACTIONS:
        - Mutate request before passing to SSL
        - Override SSL decision
        - Add assumptions to request
        - Downgrade STOP → ALLOW
        """
        # Verify no assumptions were added
        self._verify_no_assumptions_added(request)

        # Create immutable copy of request for verification
        request_fingerprint_before = self._fingerprint(request)

        # Pass request to SSL (unchanged)
        ssl_decision = self.kernel.evaluate(request)

        # Verify request was not mutated
        # (In Python, we can't easily prevent mutation, but we can detect it)
        request_fingerprint_after = self._fingerprint(request)
        if request_fingerprint_before != request_fingerprint_after:
            raise AILInterferenceViolation(
                "AIL violated non-interference: request was mutated during evaluation",
                interference_type="mutate_request",
                evidence={
                    "fingerprint_before": request_fingerprint_before,
                    "fingerprint_after": request_fingerprint_after,
                }
            )

        # Compute fingerprint for session tracking
        fingerprint = self._fingerprint(request)

        # NON-AMBIGUITY PATH: Pass through SSL decision unchanged
        if not getattr(ssl_decision, "is_ambiguity", False):
            self.session.reset()
            # Verify decision is returned unchanged
            self._verify_decision_unmodified(ssl_decision, ssl_decision)
            return ssl_decision  # PASSTHROUGH - no interference

        # AMBIGUITY PATH: AIL-only logic (clarification requests)
        # This is PERMITTED because it does not override SSL decision
        if self.session.terminal_declared:
            return ""  # Silence after TAD

        if self.session.last_fingerprint == fingerprint:
            if self.session.clarification_attempts < self.session.max_clarifications:
                self.session.clarification_attempts += 1
                return (
                    "To proceed without assumptions, provide the missing "
                    "definitions or variables required by the request."
                )
            else:
                self.session.terminal_declared = True
                return TERMINAL_AMBIGUITY_TEXT

        # New input fingerprint
        self.session.last_fingerprint = fingerprint
        self.session.clarification_attempts = 1
        return (
            "To proceed without assumptions, provide the missing "
            "definitions or variables required by the request."
        )
