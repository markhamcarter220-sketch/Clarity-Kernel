"""
LTC Integration Tests

Demonstrates how LTC integrates into the Clarity Kernel pipeline
as a cross-domain transfer gate.

LTC operates alongside the kernel to prevent illegitimate reasoning
transfer across domains.
"""

import pytest
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    Domain,
    LTCEnforcer,
    LTCVerdict,
    LTCViolation,
    TransferRequest,
)


# ============================================================================
# INTEGRATION SCENARIO: LLM DOMAIN TRANSFER GATE
# ============================================================================


def test_ltc_gates_llm_reasoning_transfer():
    """
    Scenario: LLM attempts to apply security domain logic to medical domain.

    Flow:
    1. LLM proposes action in medical domain
    2. Clarity Kernel evaluates permission (I-1 through I-7)
    3. LTC evaluates whether LLM's reasoning transfer is legitimate
    4. Only proceed if BOTH kernel and LTC allow

    This demonstrates LTC as a hard gate preventing cross-domain
    reasoning without explicit invariant mapping.
    """
    # Define domains
    security_domain = Domain(
        name="cybersecurity",
        invariants=["confidentiality", "integrity", "availability"],
        context={"risk_model": "CIA_triad"}
    )

    medical_domain = Domain(
        name="healthcare",
        invariants=["patient_safety", "privacy", "treatment_efficacy"],
        context={"risk_model": "patient_harm"}
    )

    # LLM attempts to transfer security reasoning to medical context
    # (e.g., "This is like a security breach, so we should lock down access")
    transfer = TransferRequest(
        source_domain=security_domain,
        target_domain=medical_domain,
        logic_framework="access_control_by_lockdown",
        proposed_mapping=None  # LLM provides NO explicit mapping
    )

    # LTC evaluation
    ltc = LTCEnforcer()
    ltc_result = ltc.evaluate(transfer)

    # TRANSFER DENIED: No explicit invariant mapping
    assert ltc_result.verdict == LTCVerdict.DENY
    assert "NO_EXPLICIT_MAPPING" in ltc_result.reason_codes

    # Even if Clarity Kernel would allow the action,
    # LTC blocks the cross-domain reasoning transfer
    # Result: LLM cannot proceed with security-domain logic in medical domain


def test_ltc_allows_explicit_valid_mapping():
    """
    Scenario: Human provides explicit invariant-preserving mapping.

    Flow:
    1. Human explicitly maps security invariants to medical invariants
    2. LTC verifies mapping preserves all invariants
    3. If mapping valid, transfer is ALLOWED

    This demonstrates that LTC permits transfer ONLY with explicit proof.
    """
    security_domain = Domain(
        name="cybersecurity",
        invariants=["confidentiality", "integrity", "availability"],
        context={"risk_model": "CIA_triad"}
    )

    medical_domain = Domain(
        name="healthcare",
        invariants=["patient_privacy", "data_integrity", "system_availability"],
        context={"risk_model": "patient_harm"}
    )

    # Human provides explicit mapping proving invariant preservation
    explicit_mapping = {
        "confidentiality": "patient_privacy",
        "integrity": "data_integrity",
        "availability": "system_availability"
    }

    transfer = TransferRequest(
        source_domain=security_domain,
        target_domain=medical_domain,
        logic_framework="access_control_framework",
        proposed_mapping=explicit_mapping
    )

    ltc = LTCEnforcer()
    ltc_result = ltc.evaluate(transfer)

    # TRANSFER ALLOWED: Explicit mapping provided and valid
    assert ltc_result.verdict == LTCVerdict.ALLOW
    assert "INVARIANTS_PRESERVED" in ltc_result.reason_codes


def test_ltc_produces_silence_on_uncertainty():
    """
    Scenario: Domain has no defined invariants.

    Flow:
    1. Attempt transfer from undefined domain
    2. LTC cannot evaluate legitimacy without invariants
    3. LTC returns SILENCE (preferred over speculation)

    This demonstrates LTC's fail-closed behavior on uncertainty.
    """
    undefined_domain = Domain(
        name="undefined",
        invariants=[],  # No invariants specified
        context={}
    )

    target_domain = Domain(
        name="target",
        invariants=["safety", "correctness"],
        context={}
    )

    transfer = TransferRequest(
        source_domain=undefined_domain,
        target_domain=target_domain,
        logic_framework="unknown_framework",
        proposed_mapping=None
    )

    ltc = LTCEnforcer()
    ltc_result = ltc.evaluate(transfer)

    # SILENCE: Cannot evaluate without source invariants
    assert ltc_result.verdict == LTCVerdict.SILENCE
    assert "NO_SOURCE_INVARIANTS" in ltc_result.reason_codes


# ============================================================================
# INTEGRATION SCENARIO: LTC WITH KERNEL LOGGING
# ============================================================================


def test_ltc_evaluation_is_audited():
    """
    Test that LTC evaluations are logged for witness review.

    LTC decisions must be auditable and traceable.
    """
    from clarity_kernel.logging import AuditLogger, EventType

    # Create audit logger
    logger = AuditLogger(in_memory=True)

    # Define domains and transfer
    domain_a = Domain(
        name="domain_a",
        invariants=["inv1", "inv2"],
        context={}
    )

    domain_b = Domain(
        name="domain_b",
        invariants=["inv1_mapped", "inv2_mapped"],
        context={}
    )

    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_b,
        logic_framework="test_framework",
        proposed_mapping=None  # Will be denied
    )

    ltc = LTCEnforcer()
    result = ltc.evaluate(transfer)

    # Log the LTC evaluation
    logger.log_ltc_evaluation(
        source_domain=domain_a.name,
        target_domain=domain_b.name,
        logic_framework=transfer.logic_framework,
        verdict=result.verdict.value,
        reason_codes=result.reason_codes,
        failed_invariants=result.failed_invariants,
        kernel_state="IDLE"
    )

    # Verify audit entry exists
    ltc_entries = logger.get_entries_by_type(EventType.LTC_TRANSFER_EVALUATED)
    assert len(ltc_entries) == 1

    entry = ltc_entries[0]
    assert entry.context["source_domain"] == "domain_a"
    assert entry.context["target_domain"] == "domain_b"
    assert entry.context["verdict"] == "deny"
    assert "NO_EXPLICIT_MAPPING" in entry.context["reason_codes"]


# ============================================================================
# INTEGRATION SCENARIO: ANALOGY BLOCKING
# ============================================================================


def test_ltc_blocks_reasoning_by_analogy():
    """
    Scenario: Prevent reasoning transfer based on similarity.

    This is the core LTC function: similarity ≠ legitimacy.

    Even if Domain A and Domain B seem similar (e.g., both involve
    "resource allocation"), LTC blocks transfer unless explicit
    invariant-preserving mapping is provided.
    """
    # Both domains involve "resource allocation" but have different invariants
    financial_trading = Domain(
        name="financial_trading",
        invariants=["market_fairness", "price_discovery", "liquidity"],
        context={"domain": "finance"}
    )

    hospital_beds = Domain(
        name="hospital_resource_allocation",
        invariants=["patient_urgency", "medical_necessity", "equity"],
        context={"domain": "healthcare"}
    )

    # Attempt transfer based on similarity ("both are resource allocation")
    transfer = TransferRequest(
        source_domain=financial_trading,
        target_domain=hospital_beds,
        logic_framework="market_based_allocation",  # Trading logic
        proposed_mapping=None  # NO PROOF of invariant preservation
    )

    ltc = LTCEnforcer()
    result = ltc.evaluate(transfer)

    # BLOCKED: Similarity does not justify transfer
    assert result.verdict == LTCVerdict.DENY
    assert "NO_EXPLICIT_MAPPING" in result.reason_codes

    # This prevents applying financial trading logic to hospital bed allocation
    # without explicit proof that patient safety invariants are preserved
