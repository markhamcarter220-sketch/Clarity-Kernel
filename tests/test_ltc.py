"""
Tests for LTC (Legitimate Transfer Constraint)

These tests verify that LTC correctly enforces invariant-preserving
transfer rules across domains.
"""

import pytest
from clarity_kernel import (
    Domain,
    TransferRequest,
    LTCEnforcer,
    LTCVerdict,
    LTCViolation,
    check_domain_transfer,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def domain_a():
    """Domain A with 3 invariants."""
    return Domain(
        name="domain_a",
        invariants=["invariant_1", "invariant_2", "invariant_3"],
        context={"type": "source"}
    )


@pytest.fixture
def domain_b_compatible():
    """Domain B compatible with Domain A (has all mapped invariants)."""
    return Domain(
        name="domain_b",
        invariants=["invariant_1_mapped", "invariant_2_mapped", "invariant_3_mapped"],
        context={"type": "target"}
    )


@pytest.fixture
def domain_c_incompatible():
    """Domain C incompatible with Domain A (missing some invariants)."""
    return Domain(
        name="domain_c",
        invariants=["invariant_1_mapped", "invariant_2_mapped"],  # Missing invariant_3
        context={"type": "target"}
    )


@pytest.fixture
def ltc_enforcer():
    """LTC enforcer instance."""
    return LTCEnforcer()


# ============================================================================
# TEST: ILLEGITIMATE TRANSFER (NO MAPPING)
# ============================================================================


def test_deny_transfer_without_explicit_mapping(ltc_enforcer, domain_a, domain_b_compatible):
    """
    Test that transfer is DENIED when no explicit mapping is provided.

    This is the core LTC requirement: similarity does not imply legitimacy.
    """
    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_b_compatible,
        logic_framework="pattern_matching_framework",
        proposed_mapping=None  # NO MAPPING
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.DENY
    assert "NO_EXPLICIT_MAPPING" in result.reason_codes
    assert len(result.failed_invariants) == 3  # All invariants fail without mapping


def test_deny_transfer_with_incomplete_mapping(ltc_enforcer, domain_a, domain_b_compatible):
    """
    Test that transfer is DENIED when mapping is incomplete.

    If even one invariant is unmapped, transfer is illegitimate.
    """
    incomplete_mapping = {
        "invariant_1": "invariant_1_mapped",
        "invariant_2": "invariant_2_mapped",
        # invariant_3 MISSING
    }

    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_b_compatible,
        logic_framework="incomplete_framework",
        proposed_mapping=incomplete_mapping
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.DENY
    assert "UNMAPPED_INVARIANT:invariant_3" in result.reason_codes
    assert "invariant_3" in result.failed_invariants


def test_deny_transfer_when_target_lacks_invariant(ltc_enforcer, domain_a, domain_c_incompatible):
    """
    Test that transfer is DENIED when target domain lacks required invariant.

    Even with explicit mapping, transfer fails if target cannot satisfy invariants.
    """
    mapping = {
        "invariant_1": "invariant_1_mapped",
        "invariant_2": "invariant_2_mapped",
        "invariant_3": "invariant_3_mapped",  # Mapped, but target doesn't have this
    }

    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_c_incompatible,
        logic_framework="invalid_framework",
        proposed_mapping=mapping
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.DENY
    assert "MISSING_TARGET_INVARIANT:invariant_3_mapped" in result.reason_codes
    assert "invariant_3" in result.failed_invariants


# ============================================================================
# TEST: SILENCE ON MISSING INFORMATION
# ============================================================================


def test_silence_when_no_source_invariants(ltc_enforcer, domain_b_compatible):
    """
    Test that LTC returns SILENCE when source has no invariants.

    Cannot evaluate legitimacy without knowing what must be preserved.
    """
    empty_domain = Domain(
        name="empty_domain",
        invariants=[],  # NO INVARIANTS
        context={}
    )

    transfer = TransferRequest(
        source_domain=empty_domain,
        target_domain=domain_b_compatible,
        logic_framework="unknown_framework",
        proposed_mapping=None
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.SILENCE
    assert "NO_SOURCE_INVARIANTS" in result.reason_codes


# ============================================================================
# TEST: LEGITIMATE TRANSFER (ALLOW)
# ============================================================================


def test_allow_transfer_with_valid_mapping(ltc_enforcer, domain_a, domain_b_compatible):
    """
    Test that transfer is ALLOWED when explicit valid mapping is provided.

    This is the ONLY case where transfer is legitimate.
    """
    valid_mapping = {
        "invariant_1": "invariant_1_mapped",
        "invariant_2": "invariant_2_mapped",
        "invariant_3": "invariant_3_mapped",
    }

    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_b_compatible,
        logic_framework="legitimate_framework",
        proposed_mapping=valid_mapping
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.ALLOW
    assert "INVARIANTS_PRESERVED" in result.reason_codes
    assert len(result.failed_invariants) == 0
    assert result.required_mapping == valid_mapping


def test_allow_same_domain_transfer(ltc_enforcer, domain_a):
    """
    Test that transfer within the same domain is ALLOWED.

    No transfer actually occurs - same domain, no mapping needed.
    """
    transfer = TransferRequest(
        source_domain=domain_a,
        target_domain=domain_a,  # SAME DOMAIN
        logic_framework="internal_framework",
        proposed_mapping=None
    )

    result = ltc_enforcer.evaluate(transfer)

    assert result.verdict == LTCVerdict.ALLOW
    assert "SAME_DOMAIN" in result.reason_codes


# ============================================================================
# TEST: CONVENIENCE FUNCTION
# ============================================================================


def test_check_domain_transfer_convenience_function(domain_a, domain_b_compatible):
    """
    Test convenience function for domain transfer checking.
    """
    mapping = {
        "invariant_1": "invariant_1_mapped",
        "invariant_2": "invariant_2_mapped",
        "invariant_3": "invariant_3_mapped",
    }

    result = check_domain_transfer(
        source_domain=domain_a,
        target_domain=domain_b_compatible,
        logic_framework="test_framework",
        proposed_mapping=mapping
    )

    assert result.verdict == LTCVerdict.ALLOW


# ============================================================================
# TEST: REQUIRED MAPPING TEMPLATE
# ============================================================================


def test_require_explicit_mapping_template(ltc_enforcer, domain_a, domain_b_compatible):
    """
    Test that LTC can generate template for required mapping.

    This does NOT infer the mapping - it only shows what must be provided.
    """
    template = ltc_enforcer.require_explicit_mapping(domain_a, domain_b_compatible)

    assert "invariant_1" in template
    assert "invariant_2" in template
    assert "invariant_3" in template
    assert template["invariant_1"] is None  # Must be explicitly provided
    assert template["invariant_2"] is None
    assert template["invariant_3"] is None
