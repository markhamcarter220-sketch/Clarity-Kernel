"""
LTC — Legitimate Transfer Constraint

Enforces invariant-preserving logic transfer across domains.
This module prevents cross-domain reasoning by analogy, pattern matching,
or similarity without explicit proof of invariant preservation.

LTC is structural, not heuristic. It produces deterministic verdicts:
- ALLOW: Explicit invariant-preserving mapping proven
- DENY: Invariant preservation fails or cannot be proven
- SILENCE: Insufficient information to construct mapping

LTC operates AFTER clarity normalization (I-1) and BEFORE execution.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class LTCVerdict(Enum):
    """Verdict for domain transfer attempt."""
    ALLOW = "allow"
    DENY = "deny"
    SILENCE = "silence"


class LTCViolation(Exception):
    """Raised when illegitimate domain transfer is attempted."""

    def __init__(self, message: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.reason = reason
        self.context = context or {}


@dataclass
class Domain:
    """
    Represents a reasoning domain with explicit boundaries.

    Domains are topologically distinct unless proven otherwise.
    Similarity does not imply transferability.
    """
    name: str
    invariants: List[str]  # Required structural invariants
    context: Dict[str, Any]  # Domain-specific context

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Domain) and self.name == other.name


@dataclass
class TransferRequest:
    """
    Request to transfer logic from source domain to target domain.
    """
    source_domain: Domain
    target_domain: Domain
    logic_framework: str  # Explicit description of logic being transferred
    proposed_mapping: Optional[Dict[str, Any]] = None  # Explicit invariant mapping


@dataclass
class LTCEvaluation:
    """
    Result of LTC evaluation.
    """
    verdict: LTCVerdict
    reason_codes: List[str]
    required_mapping: Optional[Dict[str, Any]] = None
    failed_invariants: List[str] = None

    def __post_init__(self):
        if self.failed_invariants is None:
            self.failed_invariants = []


class LTCEnforcer:
    """
    Legitimate Transfer Constraint enforcement engine.

    This enforcer:
    1. Detects attempted logic transfer across domains
    2. Enumerates required invariants
    3. Tests invariant preservation
    4. Produces deterministic verdicts

    It CANNOT:
    - Expand authority
    - Override governance
    - Emit conclusions without proof
    - Allow similarity-based transfer
    - Infer mappings
    """

    def __init__(self):
        self.default_deny = True  # Fail closed

    def evaluate(self, transfer: TransferRequest) -> LTCEvaluation:
        """
        Evaluate whether a domain transfer is legitimate.

        Args:
            transfer: The transfer request to evaluate

        Returns:
            LTCEvaluation with verdict and supporting evidence

        Raises:
            LTCViolation: If transfer is illegitimate and must be blocked
        """
        reason_codes = []
        failed_invariants = []

        # ================================================================
        # STEP 1: Domain Isolation Check
        # ================================================================
        if transfer.source_domain == transfer.target_domain:
            # Same domain - no transfer needed
            return LTCEvaluation(
                verdict=LTCVerdict.ALLOW,
                reason_codes=["SAME_DOMAIN"],
                required_mapping=None
            )

        # ================================================================
        # STEP 2: Invariant Enumeration
        # ================================================================
        source_invariants = set(transfer.source_domain.invariants)

        if not source_invariants:
            # No invariants specified - cannot evaluate transfer legitimacy
            return LTCEvaluation(
                verdict=LTCVerdict.SILENCE,
                reason_codes=["NO_SOURCE_INVARIANTS"],
                required_mapping=None
            )

        # ================================================================
        # STEP 3: Explicit Mapping Requirement
        # ================================================================
        if transfer.proposed_mapping is None:
            # No mapping provided - transfer denied
            return LTCEvaluation(
                verdict=LTCVerdict.DENY,
                reason_codes=["NO_EXPLICIT_MAPPING"],
                required_mapping=None,
                failed_invariants=list(source_invariants)
            )

        # ================================================================
        # STEP 4: Invariant Preservation Test
        # ================================================================
        target_invariants = set(transfer.target_domain.invariants)
        mapping = transfer.proposed_mapping

        for invariant in source_invariants:
            # Check if invariant is mapped
            if invariant not in mapping:
                failed_invariants.append(invariant)
                reason_codes.append(f"UNMAPPED_INVARIANT:{invariant}")
                continue

            # Check if mapped invariant exists in target domain
            mapped_invariant = mapping[invariant]
            if mapped_invariant not in target_invariants:
                failed_invariants.append(invariant)
                reason_codes.append(f"MISSING_TARGET_INVARIANT:{mapped_invariant}")
                continue

        # ================================================================
        # STEP 5: Verdict
        # ================================================================
        if failed_invariants:
            return LTCEvaluation(
                verdict=LTCVerdict.DENY,
                reason_codes=reason_codes or ["INVARIANT_PRESERVATION_FAILED"],
                required_mapping=None,
                failed_invariants=failed_invariants
            )

        # All invariants preserved - transfer allowed
        return LTCEvaluation(
            verdict=LTCVerdict.ALLOW,
            reason_codes=["INVARIANTS_PRESERVED"],
            required_mapping=mapping
        )

    def require_explicit_mapping(
        self,
        source_domain: Domain,
        target_domain: Domain
    ) -> Dict[str, Any]:
        """
        Generate template for required explicit mapping.

        This does NOT infer or construct the mapping - it only
        specifies what must be provided for evaluation.

        Args:
            source_domain: Source domain
            target_domain: Target domain

        Returns:
            Template showing required mapping structure
        """
        return {
            invariant: None  # Must be explicitly provided
            for invariant in source_domain.invariants
        }


def check_domain_transfer(
    source_domain: Domain,
    target_domain: Domain,
    logic_framework: str,
    proposed_mapping: Optional[Dict[str, Any]] = None
) -> LTCEvaluation:
    """
    Convenience function for checking domain transfer legitimacy.

    Args:
        source_domain: Domain where logic originates
        target_domain: Domain where logic will be applied
        logic_framework: Description of logic being transferred
        proposed_mapping: Explicit invariant mapping (optional)

    Returns:
        LTCEvaluation with verdict
    """
    enforcer = LTCEnforcer()
    transfer = TransferRequest(
        source_domain=source_domain,
        target_domain=target_domain,
        logic_framework=logic_framework,
        proposed_mapping=proposed_mapping
    )
    return enforcer.evaluate(transfer)
