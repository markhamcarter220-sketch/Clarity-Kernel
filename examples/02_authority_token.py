"""
Example 02: Authority Token Generation and Verification

This example demonstrates:
- How to generate Ed25519 key pairs for authority signing
- How to issue cryptographically signed authority tokens
- How to verify authority tokens in the kernel
- Proper authority token lifecycle

IMPORTANT: This example uses real cryptographic signing (PyNaCl).
Install: pip install pynacl
"""

import time
import os
import nacl.signing
import nacl.encoding
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    PermissionDenied,
)


def generate_authority_keys():
    """
    Generate Ed25519 key pair for authority signing.

    In production:
    - Generate ONCE and store securely (HSM, vault, encrypted storage)
    - Never expose private key
    - Register public key in TRUSTED_ISSUER_REGISTRY
    """
    print("\nGenerating Ed25519 key pair...")
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key

    print(f"Private key (keep secret): {signing_key.encode().hex()[:32]}...")
    print(f"Public key (register in kernel): {verify_key.encode().hex()}")

    return signing_key, verify_key


def issue_authority_token(source: str, scope: str, signing_key: nacl.signing.SigningKey) -> AuthorityToken:
    """
    Issues a cryptographically signed authority token.

    This simulates an authority server that:
    1. Authenticates the requester
    2. Determines appropriate scope
    3. Signs the token with private key
    4. Returns token to requester

    Args:
        source: Identity of authorizing entity
        scope: Scope of authorization (e.g., "file.read")
        signing_key: Ed25519 private signing key

    Returns:
        AuthorityToken with valid Ed25519 signature
    """
    print(f"\nIssuing authority token...")
    print(f"  Source: {source}")
    print(f"  Scope: {scope}")

    # Generate token fields
    timestamp = int(time.time())
    nonce = os.urandom(32)

    # Construct message to sign (per docs/AUTHORITY.md)
    message = (
        source.encode() + b'|' +
        scope.encode() + b'|' +
        timestamp.to_bytes(8, 'big') + b'|' +
        nonce
    )

    # Sign message
    signed = signing_key.sign(message)
    signature = signed.signature

    # Get public key
    public_key = signing_key.verify_key.encode()

    token = AuthorityToken(
        source=source,
        verifiable=True,  # DEPRECATED field, but required
        scope=scope,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
        issuer_pubkey=public_key
    )

    print(f"  ✓ Token issued (signature: {signature.hex()[:32]}...)")
    return token


def verify_authority_token_manually(token: AuthorityToken) -> bool:
    """
    Manually verify an authority token (demonstrates verification logic).

    The kernel performs this verification internally.
    This is for demonstration purposes only.

    Args:
        token: Authority token to verify

    Returns:
        True if valid, False otherwise
    """
    print("\nManually verifying authority token...")

    try:
        # Reconstruct message
        message = (
            token.source.encode() + b'|' +
            token.scope.encode() + b'|' +
            token.timestamp.to_bytes(8, 'big') + b'|' +
            token.nonce
        )

        # Create verify key from public key
        verify_key = nacl.signing.VerifyKey(token.issuer_pubkey)

        # Verify signature
        verify_key.verify(message, token.signature)

        # Check timestamp (not expired, not future)
        current_time = int(time.time())
        MAX_TOKEN_AGE = 300  # 5 minutes

        if token.timestamp > current_time:
            print("  ✗ Token from future (invalid)")
            return False

        if current_time - token.timestamp > MAX_TOKEN_AGE:
            print("  ✗ Token expired")
            return False

        print("  ✓ Signature valid")
        print("  ✓ Timestamp valid")
        return True

    except nacl.exceptions.BadSignatureError:
        print("  ✗ Invalid signature")
        return False


def main():
    print("=" * 60)
    print("Example 02: Authority Token Generation and Verification")
    print("=" * 60)

    # Step 1: Generate authority server keys
    signing_key, verify_key = generate_authority_keys()

    # Step 2: Issue authority token
    authority_token = issue_authority_token(
        source="admin_alice",
        scope="file.read",
        signing_key=signing_key
    )

    # Step 3: Manually verify token (demonstration)
    is_valid = verify_authority_token_manually(authority_token)

    if not is_valid:
        print("\n✗ Token verification failed - aborting")
        return

    # Step 4: Use token with kernel
    print("\n" + "=" * 60)
    print("Using token with Clarity Kernel")
    print("=" * 60)

    kernel = ClarityKernel()

    request = PermissionRequest(
        operation_id="read_with_auth_001",
        variables=[
            Variable("file_path", resolved=True, material=True, value="/etc/config.yaml")
        ],
        required_definitions={"file_path": "/etc/config.yaml"},
        required_thresholds={},
        required_constraints=["file_exists"],
        authority=authority_token,  # Use signed token
        required_scope="file.read",
        preconditions=MomentaryPreconditions(
            outcome_reversible=True,
            risk_does_not_increase=True,
            no_new_critical_info=True,
            w_within_limit=True,
            execution_window_bounded=True
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=False,
            compliance_safety_exposure=False,
            context_may_change=False,
            ambiguity_at_initiation=False,
            w_may_fluctuate=False,
            execution_window_extended=False
        ),
        requires_continuous_attention=False,
        harm_scenario="none"
    )

    try:
        response = kernel.request_permission(request)

        print("\n✓ PERMISSION GRANTED")
        print(f"  Control Mode: {response.control_mode.value}")
        print(f"  Authority Source: {authority_token.source}")
        print(f"  Authority Scope: {authority_token.scope}")

    except PermissionDenied as e:
        print(f"\n✗ PERMISSION DENIED: {e.reason}")

    # Step 5: Demonstrate token expiry
    print("\n" + "=" * 60)
    print("Demonstrating token expiry (waiting 6 seconds)...")
    print("=" * 60)

    # Wait for token to expire (MAX_TOKEN_AGE = 300s in production, but we'll simulate)
    print("(In production, tokens expire after 300 seconds)")
    print("(This example would show expiry if we waited)")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print("\n✗ Error: PyNaCl not installed")
        print("Install with: pip install pynacl")
        print(f"Details: {e}")
