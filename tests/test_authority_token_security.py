"""
Tests for AuthorityToken security properties.

This test suite proves that authority is a real security primitive by testing:
1. Token structure validation (byte lengths, field presence)
2. Expiry enforcement (MAX_TOKEN_AGE)
3. Nonce replay prevention
4. Scope hierarchical matching
5. Issuer trust verification
6. Signature verification (when PyNaCl available)
7. Integration with validate_authority()
"""

import pytest
import time
import os
from clarity_kernel import (
    AuthorityToken,
    TokenValidationError,
    AuthorityInvariantViolation,
    validate_authority,
    register_trusted_issuer,
    is_trusted_issuer,
    check_nonce_replay,
    check_scope_hierarchy,
    verify_token_signature,
    validate_token_expiry,
    MAX_TOKEN_AGE,
    TRUSTED_ISSUER_REGISTRY,
)


# ============================================================================
# TOKEN STRUCTURE VALIDATION
# ============================================================================

def test_token_requires_64_byte_signature():
    """Token construction must enforce 64-byte Ed25519 signature."""
    with pytest.raises(ValueError, match="Invalid signature length"):
        AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 32,  # Too short
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 32
        )


def test_token_requires_32_byte_nonce():
    """Token construction must enforce 32-byte nonce."""
    with pytest.raises(ValueError, match="Invalid nonce length"):
        AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 64,
            timestamp=int(time.time()),
            nonce=b'\x00' * 16,  # Too short
            issuer_pubkey=b'\x00' * 32
        )


def test_token_requires_32_byte_pubkey():
    """Token construction must enforce 32-byte Ed25519 public key."""
    with pytest.raises(ValueError, match="Invalid issuer_pubkey length"):
        AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 64,
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 16  # Too short
        )


def test_token_requires_positive_timestamp():
    """Token timestamp must be positive Unix timestamp."""
    with pytest.raises(ValueError, match="Invalid timestamp"):
        AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 64,
            timestamp=-100,  # Invalid
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 32
        )


def test_token_requires_non_empty_source():
    """Token source cannot be empty."""
    with pytest.raises(ValueError, match="source cannot be empty"):
        AuthorityToken(
            source="",  # Empty
            scope="file.read",
            signature=b'\x00' * 64,
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 32
        )


def test_token_requires_non_empty_scope():
    """Token scope cannot be empty."""
    with pytest.raises(ValueError, match="scope cannot be empty"):
        AuthorityToken(
            source="admin",
            scope="",  # Empty
            signature=b'\x00' * 64,
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 32
        )


def test_valid_token_construction():
    """Valid token should construct successfully."""
    token = AuthorityToken(
        source="admin_alice",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )

    assert token.source == "admin_alice"
    assert token.scope == "file.read"
    assert len(token.signature) == 64
    assert len(token.nonce) == 32
    assert len(token.issuer_pubkey) == 32


# ============================================================================
# TOKEN EXPIRY VALIDATION
# ============================================================================

def test_token_expiry_rejects_future_timestamp():
    """Tokens from the future should be rejected (clock skew attack)."""
    future_token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()) + 3600,  # 1 hour in future
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )

    with pytest.raises(TokenValidationError, match="timestamp is in the future"):
        validate_token_expiry(future_token)


def test_token_expiry_allows_small_clock_skew():
    """Small clock skew (< 60s) should be allowed."""
    token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()) + 30,  # 30s in future (within tolerance)
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )

    # Should not raise
    validate_token_expiry(token)


def test_token_expiry_rejects_old_tokens():
    """Tokens older than MAX_TOKEN_AGE should be rejected."""
    old_token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()) - (MAX_TOKEN_AGE + 100),  # Expired
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )

    with pytest.raises(TokenValidationError, match="Token expired"):
        validate_token_expiry(old_token)


def test_token_expiry_accepts_fresh_tokens():
    """Fresh tokens should pass expiry check."""
    fresh_token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()) - 10,  # 10 seconds old
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )

    # Should not raise
    validate_token_expiry(fresh_token)


# ============================================================================
# NONCE REPLAY PREVENTION
# ============================================================================

def test_nonce_replay_detection():
    """Same nonce used twice should be detected as replay attack."""
    nonce = os.urandom(32)

    # First use should succeed
    assert check_nonce_replay(nonce) is True

    # Second use should fail (replay)
    assert check_nonce_replay(nonce) is False


def test_different_nonces_both_accepted():
    """Different nonces should both be accepted."""
    nonce1 = os.urandom(32)
    nonce2 = os.urandom(32)

    assert check_nonce_replay(nonce1) is True
    assert check_nonce_replay(nonce2) is True


# ============================================================================
# SCOPE HIERARCHY MATCHING
# ============================================================================

def test_scope_exact_match():
    """Exact scope match should pass."""
    assert check_scope_hierarchy("file.read", "file.read") is True


def test_scope_wildcard_grants_all():
    """Wildcard scope (*) should grant everything."""
    assert check_scope_hierarchy("*", "file.read") is True
    assert check_scope_hierarchy("*", "medical.prescribe") is True
    assert check_scope_hierarchy("*", "anything") is True


def test_scope_hierarchical_wildcard():
    """Hierarchical wildcard (file.*) should grant all file operations."""
    assert check_scope_hierarchy("file.*", "file.read") is True
    assert check_scope_hierarchy("file.*", "file.write") is True
    assert check_scope_hierarchy("file.*", "file.delete") is True


def test_scope_hierarchical_wildcard_does_not_grant_sibling():
    """Hierarchical wildcard should not grant sibling scopes."""
    assert check_scope_hierarchy("file.*", "medical.read") is False


def test_scope_mismatch_fails():
    """Mismatched scopes should fail."""
    assert check_scope_hierarchy("file.read", "file.write") is False
    assert check_scope_hierarchy("file.read", "medical.read") is False


def test_scope_narrower_does_not_grant_broader():
    """Narrower scope should not grant broader scope."""
    assert check_scope_hierarchy("file.read", "file.*") is False


# ============================================================================
# ISSUER TRUST VERIFICATION
# ============================================================================

def test_issuer_registration():
    """Issuer registration should add to trusted registry."""
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_issuer", max_scope="*")

    assert is_trusted_issuer(pubkey) is True


def test_unregistered_issuer_not_trusted():
    """Unregistered issuers should not be trusted."""
    unknown_pubkey = os.urandom(32)
    assert is_trusted_issuer(unknown_pubkey) is False


def test_register_issuer_validates_pubkey_length():
    """Registering issuer with invalid pubkey should fail."""
    with pytest.raises(ValueError, match="Invalid public key length"):
        register_trusted_issuer(b'\x00' * 16, "bad_issuer")  # Too short


# ============================================================================
# SIGNATURE VERIFICATION
# ============================================================================

def test_signature_verification_requires_pynacl():
    """
    Test signature verification behavior.

    If PyNaCl is installed, verification should work.
    If not, should warn and skip verification.
    """
    try:
        import nacl.signing

        # PyNaCl is available - test real signature verification
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key

        timestamp = int(time.time())
        nonce = os.urandom(32)
        source = "admin_alice"
        scope = "file.read"

        # Create message to sign
        message = (
            source.encode() + b'|' +
            scope.encode() + b'|' +
            timestamp.to_bytes(8, 'big') + b'|' +
            nonce
        )

        # Sign message
        signed = signing_key.sign(message)

        # Create valid token
        token = AuthorityToken(
            source=source,
            scope=scope,
            signature=signed.signature,
            timestamp=timestamp,
            nonce=nonce,
            issuer_pubkey=verify_key.encode()
        )

        # Should verify successfully
        assert verify_token_signature(token) is True

    except ImportError:
        # PyNaCl not available - test fallback behavior
        token = AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 64,
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=b'\x00' * 32
        )

        # Should warn and skip verification
        with pytest.warns(RuntimeWarning, match="PyNaCl not installed"):
            assert verify_token_signature(token) is True


def test_signature_verification_detects_forgery():
    """
    Test that forged signatures are rejected.

    Only runs if PyNaCl is available.
    """
    try:
        import nacl.signing

        # Generate legitimate signing key
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key

        # Create token with WRONG signature
        token = AuthorityToken(
            source="admin",
            scope="file.read",
            signature=b'\x00' * 64,  # Invalid signature
            timestamp=int(time.time()),
            nonce=os.urandom(32),
            issuer_pubkey=verify_key.encode()
        )

        # Should detect forgery
        with pytest.raises(TokenValidationError, match="Signature verification failed"):
            verify_token_signature(token)

    except ImportError:
        pytest.skip("PyNaCl not installed - cannot test signature verification")


# ============================================================================
# INTEGRATED VALIDATION
# ============================================================================

def test_validate_authority_with_valid_token():
    """
    Test complete authority validation with valid token.
    """
    # Register trusted issuer
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_authority", max_scope="*")

    # Create valid token
    token = AuthorityToken(
        source="admin_alice",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=pubkey
    )

    # Should pass validation (skipping signature verification for test)
    validate_authority(token, "file.read", skip_signature_verification=True)


def test_validate_authority_rejects_expired_token():
    """Test that validate_authority rejects expired tokens."""
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_authority")

    expired_token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()) - (MAX_TOKEN_AGE + 100),
        nonce=os.urandom(32),
        issuer_pubkey=pubkey
    )

    with pytest.raises(TokenValidationError, match="Token expired"):
        validate_authority(expired_token, "file.read", skip_signature_verification=True)


def test_validate_authority_rejects_nonce_replay():
    """Test that validate_authority detects nonce replay."""
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_authority")

    nonce = os.urandom(32)
    token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=nonce,
        issuer_pubkey=pubkey
    )

    # First use should succeed
    validate_authority(token, "file.read", skip_signature_verification=True)

    # Create second token with same nonce
    token2 = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=nonce,  # Same nonce - replay
        issuer_pubkey=pubkey
    )

    # Should detect replay
    with pytest.raises(TokenValidationError, match="Nonce replay detected"):
        validate_authority(token2, "file.read", skip_signature_verification=True)


def test_validate_authority_rejects_untrusted_issuer():
    """Test that validate_authority rejects untrusted issuers."""
    untrusted_pubkey = os.urandom(32)  # Not registered

    token = AuthorityToken(
        source="admin",
        scope="file.read",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=untrusted_pubkey
    )

    with pytest.raises(TokenValidationError, match="Issuer not in trusted registry"):
        validate_authority(token, "file.read", skip_signature_verification=True)


def test_validate_authority_rejects_insufficient_scope():
    """Test that validate_authority enforces scope matching."""
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_authority")

    token = AuthorityToken(
        source="admin",
        scope="file.read",  # Only read
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=pubkey
    )

    # Should fail - need write but only have read
    with pytest.raises(AuthorityInvariantViolation, match="scope insufficient"):
        validate_authority(token, "file.write", skip_signature_verification=True)


def test_validate_authority_accepts_wildcard_scope():
    """Test that wildcard scope grants all operations."""
    pubkey = os.urandom(32)
    register_trusted_issuer(pubkey, "test_authority")

    # Test wildcard scope with different nonces (each token can only be used once)
    wildcard_token1 = AuthorityToken(
        source="admin",
        scope="*",  # Wildcard
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=pubkey
    )

    wildcard_token2 = AuthorityToken(
        source="admin",
        scope="*",  # Wildcard
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),  # Different nonce
        issuer_pubkey=pubkey
    )

    # Should pass for any required scope
    validate_authority(wildcard_token1, "file.read", skip_signature_verification=True)
    validate_authority(wildcard_token2, "medical.prescribe", skip_signature_verification=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
