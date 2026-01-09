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
"""

import warnings

from typing import Optional
import hashlib

from clarity_kernel.ssl import ClarityKernel


# Issue deprecation warning on import
warnings.warn(
    "AIL (Adaptive Interaction Layer) is NON-NORMATIVE and may be removed in future versions. "
    "For production use, interact directly with ClarityKernel (SSL). "
    "See SPECIFICATION.md Section 4.2.",
    DeprecationWarning,
    stacklevel=2
)


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
    def __init__(self, kernel: ClarityKernel, session: Optional[AILSession] = None):
        self.kernel = kernel
        self.session = session or AILSession()

    def _fingerprint(self, payload) -> str:
        data = repr(payload).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def step(self, request):
        fingerprint = self._fingerprint(request)

        decision = self.kernel.evaluate(request)

        # Pass through all non-ambiguity decisions unchanged
        if not getattr(decision, "is_ambiguity", False):
            self.session.reset()
            return decision

        # Ambiguity handling (AIL-only)
        if self.session.terminal_declared:
            return ""

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
