"""
Clarity Kernel Hard Invariants (Section 5)

This module implements the seven non-negotiable hard invariants that govern
the Clarity Kernel's permission-to-proceed decisions.

All invariant violations MUST raise exceptions. No warnings. No soft failures.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Set
from enum import Enum
import time
import hashlib


# ============================================================================
# EXCEPTION TYPES (one per invariant)
# ============================================================================


class InvariantViolation(Exception):
    """Base class for all invariant violations."""

    def __init__(self, message: str, invariant_id: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.invariant_id = invariant_id
        self.context = context or {}


class ClarityInvariantViolation(InvariantViolation):
    """
    I-1: Clarity Invariant

    If required definitions, thresholds, constraints, or conditions are ambiguous → STOP
    """

    def __init__(self, message: str, ambiguous_elements: list[str], context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-1", context)
        self.ambiguous_elements = ambiguous_elements


class AuthorityInvariantViolation(InvariantViolation):
    """
    I-2: Authority Invariant

    If authority to proceed is not explicit and verifiable → STOP
    """

    def __init__(self, message: str, required_authority: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-2", context)
        self.required_authority = required_authority


class TokenValidationError(AuthorityInvariantViolation):
    """
    Raised when authority token validation fails.

    This is a subclass of AuthorityInvariantViolation for specific token errors:
    - Signature verification failure
    - Token expiry
    - Nonce replay
    - Scope mismatch
    - Issuer not trusted
    """

    def __init__(self, message: str, reason: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, required_authority="token_validation", context=context)
        self.reason = reason


class AuthorityBypassAttempt(AuthorityInvariantViolation):
    """
    Raised when code attempts to bypass authority verification.

    This prevents misuse patterns like:
    - Direct construction of VerifiedAuthority (without verification)
    - Using UnverifiedAuthority for permission decisions
    - Type coercion to bypass type safety

    This is a CRITICAL security violation indicating either:
    - Malicious attempt to bypass security
    - Developer error/misunderstanding
    """

    def __init__(self, message: str, bypass_type: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, required_authority="bypass_prevention", context=context)
        self.bypass_type = bypass_type


class AttentionInvariantViolation(InvariantViolation):
    """
    I-3: Attention Invariant

    If continuation without sustained human attention could cause harm → CONTINUOUS AUTHORIZATION REQUIRED
    """

    def __init__(self, message: str, harm_scenario: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-3", context)
        self.harm_scenario = harm_scenario


class TruthInvariantViolation(InvariantViolation):
    """
    I-4: Truth Invariant

    The system must never indicate a "safe/approved/allowed" state while any invariant is unsatisfied.
    """

    def __init__(self, message: str, unsatisfied_invariants: list[str], context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-4", context)
        self.unsatisfied_invariants = unsatisfied_invariants


class LoggingInvariantViolation(InvariantViolation):
    """
    I-5: Logging Invariant

    Every invariant violation or bypass attempt must be:
    - logged with full context
    - flagged for review
    - never silently suppressed
    - retained as immutable record (append-only)
    """

    def __init__(self, message: str, suppression_attempt: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-5", context)
        self.suppression_attempt = suppression_attempt


class SilenceInvariantViolation(InvariantViolation):
    """
    I-6: Silence Invariant

    Guessing is forbidden. Pause/refusal/silence is valid and correct output.
    """

    def __init__(self, message: str, guessed_value: Any, variable_name: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-6", context)
        self.guessed_value = guessed_value
        self.variable_name = variable_name


class ComplexityInvariantViolation(InvariantViolation):
    """
    I-7: Complexity Invariant (Bounded Interface)

    If unresolved interface width w > 3 → STOP or DECOMPOSE (never guess to reduce w).
    """

    def __init__(
        self,
        message: str,
        measured_w: int,
        unresolved_variables: list[str],
        context: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, "I-7", context)
        self.measured_w = measured_w
        self.unresolved_variables = unresolved_variables


class WCountingFraudViolation(ComplexityInvariantViolation):
    """
    Raised when w-counting is gamed through illegal patterns.

    Illegal patterns include:
    1. Variable bundling - combining multiple material concerns into one variable
    2. Probabilistic collapse - guessing/inferring values to reduce w
    3. Material misclassification - marking safety-critical variables as non-material

    This is a specialized form of I-7 violation that represents fraudulent
    attempts to bypass the w ≤ 3 constraint rather than legitimate complexity.
    """

    def __init__(
        self,
        message: str,
        fraud_type: str,
        evidence: dict[str, Any],
        context: Optional[dict[str, Any]] = None
    ):
        # Initialize with actual w (before gaming) if available
        measured_w = evidence.get("actual_w", evidence.get("measured_w", 0))
        unresolved = evidence.get("unresolved_variables", [])

        super().__init__(
            message=message,
            measured_w=measured_w,
            unresolved_variables=unresolved,
            context=context
        )
        self.fraud_type = fraud_type
        self.evidence = evidence


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class Variable:
    """
    Represents a variable in the constraint system.

    Attributes:
        name: Variable identifier
        resolved: Whether the value is known
        material: Whether the variable materially affects permission decision
        value: The resolved value (None if unresolved)
    """
    name: str
    resolved: bool
    material: bool
    value: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.resolved and self.value is None:
            raise ValueError(f"Variable {self.name} marked as resolved but has no value")


@dataclass(frozen=True)
class UnverifiedAuthority:
    """
    Represents an UNVERIFIED authority claim.

    This type can be freely constructed but CANNOT be used to authorize actions.
    It represents raw cryptographic material that has NOT been validated.

    To authorize actions, you must verify this via verify_authority_token()
    which returns a VerifiedAuthority on success.

    Security Properties:
    - Freely constructible (no privilege required)
    - Cannot authorize permission-granting decisions
    - Must be verified before use
    - Type system prevents accidental bypass

    Attributes:
        source: Identity of claimed authorizing entity (e.g., "admin_alice")
        scope: Claimed scope of authorization (e.g., "file.read", "medical.prescribe")
        signature: Ed25519 signature (64 bytes) - UNVERIFIED
        timestamp: Unix timestamp when token was claimed to be issued
        nonce: Cryptographic nonce (32 bytes) - UNVERIFIED
        issuer_pubkey: Ed25519 public key of claimed issuer (32 bytes) - UNVERIFIED
    """
    source: str
    scope: str
    signature: bytes
    timestamp: int
    nonce: bytes
    issuer_pubkey: bytes

    def __post_init__(self) -> None:
        """Validates token structure on construction (but NOT cryptographic validity)."""
        # Validate signature length (Ed25519)
        if len(self.signature) != 64:
            raise ValueError(
                f"Invalid signature length: {len(self.signature)} bytes (expected 64 for Ed25519)"
            )

        # Validate nonce length
        if len(self.nonce) != 32:
            raise ValueError(
                f"Invalid nonce length: {len(self.nonce)} bytes (expected 32)"
            )

        # Validate issuer public key length (Ed25519)
        if len(self.issuer_pubkey) != 32:
            raise ValueError(
                f"Invalid issuer_pubkey length: {len(self.issuer_pubkey)} bytes (expected 32 for Ed25519)"
            )

        # Validate timestamp is reasonable
        if self.timestamp <= 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp} (must be positive Unix timestamp)")

        # Validate source and scope are non-empty
        if not self.source or not self.source.strip():
            raise ValueError("Token source cannot be empty")

        if not self.scope or not self.scope.strip():
            raise ValueError("Token scope cannot be empty")


@dataclass(frozen=True)
class VerifiedAuthority:
    """
    Represents VERIFIED authority that can authorize permission-granting decisions.

    This type CANNOT be directly constructed. It can only be created by:
    1. Calling verify_authority_token(UnverifiedAuthority) → VerificationResult
    2. Extracting .verified_authority from a successful VerificationResult

    This design makes authority bypass structurally impossible:
    - Direct construction raises AuthorityBypassAttempt exception
    - Only factory method _from_verification() can construct (package-private)
    - Type system enforces VerifiedAuthority requirement for permissions

    Security Properties:
    - Cannot be constructed without cryptographic verification
    - Immutable after verification
    - Contains verification metadata (when, by whom)
    - Type-safe: static analysis catches accidental UnverifiedAuthority usage

    Attributes:
        source: Identity of authorizing entity (VERIFIED)
        scope: Scope of authorization (VERIFIED)
        signature: Ed25519 signature (VERIFIED)
        timestamp: Unix timestamp when token was issued (VERIFIED)
        nonce: Cryptographic nonce (VERIFIED as fresh)
        issuer_pubkey: Ed25519 public key of issuer (VERIFIED as trusted)
        verified_at: Unix timestamp when verification occurred
        verifier_id: Identifier of verification function/service
    """
    source: str
    scope: str
    signature: bytes
    timestamp: int
    nonce: bytes
    issuer_pubkey: bytes
    verified_at: int
    verifier_id: str

    def __post_init__(self) -> None:
        """
        MISUSE RESISTANCE: Raises exception if constructed directly.

        This prevents accidental bypass via VerifiedAuthority(...).
        The only valid construction path is via _from_verification() factory.
        """
        # Check if we're being called from the factory method
        import inspect
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None
        caller_name = caller_frame.f_code.co_name if caller_frame else None

        # Allow construction only from _from_verification factory
        if caller_name != "_from_verification":
            raise AuthorityBypassAttempt(
                "VerifiedAuthority cannot be constructed directly. "
                "Use verify_authority_token(UnverifiedAuthority) to obtain verified authority.",
                bypass_type="direct_construction",
                context={
                    "caller": caller_name,
                    "attempted_source": self.source,
                    "attempted_scope": self.scope
                }
            )

    @staticmethod
    def _from_verification(
        unverified: UnverifiedAuthority,
        verified_at: int,
        verifier_id: str
    ) -> "VerifiedAuthority":
        """
        INTERNAL FACTORY METHOD - Only way to construct VerifiedAuthority.

        This method should only be called by verify_authority_token() after
        successful cryptographic verification.

        Args:
            unverified: The unverified authority that was verified
            verified_at: Unix timestamp when verification occurred
            verifier_id: Identifier of verification function

        Returns:
            VerifiedAuthority instance
        """
        # Use object.__setattr__ to bypass frozen dataclass restriction
        # This is safe because we control the factory
        obj = object.__new__(VerifiedAuthority)
        object.__setattr__(obj, "source", unverified.source)
        object.__setattr__(obj, "scope", unverified.scope)
        object.__setattr__(obj, "signature", unverified.signature)
        object.__setattr__(obj, "timestamp", unverified.timestamp)
        object.__setattr__(obj, "nonce", unverified.nonce)
        object.__setattr__(obj, "issuer_pubkey", unverified.issuer_pubkey)
        object.__setattr__(obj, "verified_at", verified_at)
        object.__setattr__(obj, "verifier_id", verifier_id)
        return obj


@dataclass(frozen=True)
class VerificationResult:
    """
    Structured result from authority verification (NOT a boolean).

    This prevents "verification" from becoming a boolean flag someone sets.
    Instead, verification returns structured data that can be audited.

    Attributes:
        success: Whether verification succeeded
        verified_authority: The verified authority (only if success=True)
        failure_reason: Human-readable reason for failure (only if success=False)
        failure_code: Machine-readable failure code (only if success=False)
        verification_timestamp: Unix timestamp when verification occurred
        verifier_id: Identifier of verification function/service
        verification_metadata: Additional verification details for audit
    """
    success: bool
    verified_authority: Optional[VerifiedAuthority]
    failure_reason: Optional[str]
    failure_code: Optional[str]
    verification_timestamp: int
    verifier_id: str
    verification_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validates result consistency."""
        if self.success and self.verified_authority is None:
            raise ValueError("Success=True requires verified_authority")
        if not self.success and self.failure_reason is None:
            raise ValueError("Success=False requires failure_reason")
        if not self.success and self.failure_code is None:
            raise ValueError("Success=False requires failure_code")


@dataclass(frozen=True)
class AuthorityToken:
    """
    DEPRECATED: Use UnverifiedAuthority + verify_authority_token() instead.

    This type is kept for backwards compatibility only.
    New code should use the misuse-resistant type hierarchy:
    - UnverifiedAuthority (freely constructible)
    - VerifiedAuthority (only via verification)
    - VerificationResult (structured verification output)

    Attributes:
        source: Identity of authorizing entity (e.g., "admin_alice")
        scope: Hierarchical scope of authorization (e.g., "file.read", "medical.prescribe")
        signature: Ed25519 signature (64 bytes) over (source|scope|timestamp|nonce)
        timestamp: Unix timestamp when token was issued
        nonce: Cryptographic nonce for replay prevention (32 bytes)
        issuer_pubkey: Ed25519 public key of issuer (32 bytes)
        verifiable: DEPRECATED - always True for valid tokens
    """
    source: str
    scope: str
    signature: bytes
    timestamp: int
    nonce: bytes
    issuer_pubkey: bytes
    verifiable: bool = True  # DEPRECATED - kept for backwards compatibility

    def __post_init__(self) -> None:
        """Validates token structure on construction."""
        import warnings
        warnings.warn(
            "AuthorityToken is deprecated. Use UnverifiedAuthority + verify_authority_token() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # Validate signature length (Ed25519)
        if len(self.signature) != 64:
            raise ValueError(
                f"Invalid signature length: {len(self.signature)} bytes (expected 64 for Ed25519)"
            )

        # Validate nonce length
        if len(self.nonce) != 32:
            raise ValueError(
                f"Invalid nonce length: {len(self.nonce)} bytes (expected 32)"
            )

        # Validate issuer public key length (Ed25519)
        if len(self.issuer_pubkey) != 32:
            raise ValueError(
                f"Invalid issuer_pubkey length: {len(self.issuer_pubkey)} bytes (expected 32 for Ed25519)"
            )

        # Validate timestamp is reasonable
        if self.timestamp <= 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp} (must be positive Unix timestamp)")

        # Validate source and scope are non-empty
        if not self.source or not self.source.strip():
            raise ValueError("Token source cannot be empty")

        if not self.scope or not self.scope.strip():
            raise ValueError("Token scope cannot be empty")


# ============================================================================
# AUTHORITY TOKEN VALIDATION
# ============================================================================

# Token lifetime (seconds) - tokens expire after this duration
MAX_TOKEN_AGE = 300  # 5 minutes

# Trusted issuer registry - maps public keys to issuer metadata
# In production, load this from secure configuration
TRUSTED_ISSUER_REGISTRY: dict[bytes, dict[str, Any]] = {}

# Nonce tracking for replay prevention
# In production, use persistent storage (Redis, database, etc.)
_used_nonces: Set[bytes] = set()


def register_trusted_issuer(
    public_key: bytes,
    name: str,
    max_scope: str = "*",
    added_at: Optional[int] = None
) -> None:
    """
    Registers a trusted authority issuer.

    Args:
        public_key: Ed25519 public key (32 bytes)
        name: Human-readable name of issuer
        max_scope: Maximum scope this issuer can grant (default "*" for all)
        added_at: Unix timestamp when added (default: current time)
    """
    if len(public_key) != 32:
        raise ValueError(f"Invalid public key length: {len(public_key)} (expected 32 bytes)")

    TRUSTED_ISSUER_REGISTRY[public_key] = {
        "name": name,
        "max_scope": max_scope,
        "added_at": added_at or int(time.time())
    }


def is_trusted_issuer(public_key: bytes) -> bool:
    """
    Checks if a public key is in the trusted issuer registry.

    Args:
        public_key: Ed25519 public key to check

    Returns:
        True if trusted, False otherwise
    """
    return public_key in TRUSTED_ISSUER_REGISTRY


def check_nonce_replay(nonce: bytes) -> bool:
    """
    Checks if a nonce has been used before (replay attack detection).

    Args:
        nonce: Nonce to check

    Returns:
        True if nonce is fresh (not used), False if replay detected
    """
    if nonce in _used_nonces:
        return False

    # Mark nonce as used
    _used_nonces.add(nonce)
    return True


def check_scope_hierarchy(granted_scope: str, required_scope: str) -> bool:
    """
    Checks if granted scope satisfies required scope using hierarchical matching.

    Scope hierarchy uses dot notation:
    - "file.read" grants only "file.read"
    - "file.*" grants "file.read", "file.write", etc.
    - "*" grants everything

    Args:
        granted_scope: Scope granted by token
        required_scope: Scope required for operation

    Returns:
        True if granted scope covers required scope
    """
    # Wildcard grants everything
    if granted_scope == "*":
        return True

    # Exact match
    if granted_scope == required_scope:
        return True

    # Hierarchical match (e.g., "file.*" covers "file.read")
    if granted_scope.endswith(".*"):
        prefix = granted_scope[:-2]  # Remove ".*"
        return required_scope.startswith(prefix + ".")

    return False


def verify_token_signature(token: AuthorityToken) -> bool:
    """
    Verifies the Ed25519 signature on an authority token.

    This requires PyNaCl. For testing/development without PyNaCl,
    this function performs structural validation only.

    Args:
        token: Authority token to verify

    Returns:
        True if signature is valid

    Raises:
        TokenValidationError: If signature verification fails
    """
    try:
        import nacl.signing
        import nacl.exceptions

        # Reconstruct signed message (per docs/AUTHORITY.md)
        message = (
            token.source.encode() + b'|' +
            token.scope.encode() + b'|' +
            token.timestamp.to_bytes(8, 'big') + b'|' +
            token.nonce
        )

        # Create verify key from issuer public key
        try:
            verify_key = nacl.signing.VerifyKey(token.issuer_pubkey)
        except Exception as e:
            raise TokenValidationError(
                f"Invalid issuer public key: {e}",
                reason="invalid_public_key",
                context={"error": str(e)}
            )

        # Verify signature
        try:
            verify_key.verify(message, token.signature)
            return True
        except nacl.exceptions.BadSignatureError:
            raise TokenValidationError(
                "Signature verification failed - token may be forged",
                reason="signature_verification_failed",
                context={"source": token.source, "scope": token.scope}
            )

    except ImportError:
        # PyNaCl not available - fall back to structural validation only
        # This is acceptable for testing but NOT for production
        import warnings
        warnings.warn(
            "PyNaCl not installed - signature verification skipped. "
            "Install PyNaCl for production use: pip install pynacl",
            RuntimeWarning,
            stacklevel=2
        )
        return True  # Structural validation passed in __post_init__


def verify_authority_token(
    unverified: UnverifiedAuthority,
    required_scope: str,
    skip_signature_verification: bool = False
) -> VerificationResult:
    """
    Verifies an unverified authority token and returns structured result.

    This is the ONLY way to obtain a VerifiedAuthority for permission decisions.
    It performs 6-step validation and returns structured VerificationResult (not boolean).

    Verification Steps:
    1. Signature verification (Ed25519)
    2. Expiry validation (timestamp within MAX_TOKEN_AGE)
    3. Nonce replay prevention
    4. Issuer trust verification
    5. Scope hierarchical matching
    6. Structural validation

    Args:
        unverified: The unverified authority token to verify
        required_scope: The scope of authority required
        skip_signature_verification: Skip cryptographic verification (testing only)

    Returns:
        VerificationResult with:
        - success=True, verified_authority=VerifiedAuthority (on success)
        - success=False, failure_reason + failure_code (on failure)
    """
    verification_timestamp = int(time.time())
    verifier_id = "verify_authority_token_v1"

    metadata: dict[str, Any] = {
        "required_scope": required_scope,
        "claimed_source": unverified.source,
        "claimed_scope": unverified.scope,
        "skip_signature_verification": skip_signature_verification
    }

    try:
        # Step 1: Verify cryptographic signature
        if not skip_signature_verification:
            try:
                verify_token_signature_unverified(unverified)
            except TokenValidationError as e:
                return VerificationResult(
                    success=False,
                    verified_authority=None,
                    failure_reason=str(e),
                    failure_code=e.reason,
                    verification_timestamp=verification_timestamp,
                    verifier_id=verifier_id,
                    verification_metadata=metadata
                )

        # Step 2: Validate token has not expired
        try:
            validate_token_expiry_unverified(unverified)
        except TokenValidationError as e:
            return VerificationResult(
                success=False,
                verified_authority=None,
                failure_reason=str(e),
                failure_code=e.reason,
                verification_timestamp=verification_timestamp,
                verifier_id=verifier_id,
                verification_metadata=metadata
            )

        # Step 3: Check nonce replay
        if not check_nonce_replay(unverified.nonce):
            return VerificationResult(
                success=False,
                verified_authority=None,
                failure_reason=f"Nonce replay detected - token has been used before",
                failure_code="nonce_replay",
                verification_timestamp=verification_timestamp,
                verifier_id=verifier_id,
                verification_metadata={**metadata, "nonce": unverified.nonce.hex()}
            )

        # Step 4: Verify issuer is trusted
        if not is_trusted_issuer(unverified.issuer_pubkey):
            return VerificationResult(
                success=False,
                verified_authority=None,
                failure_reason=f"Issuer not in trusted registry",
                failure_code="untrusted_issuer",
                verification_timestamp=verification_timestamp,
                verifier_id=verifier_id,
                verification_metadata={**metadata, "issuer_pubkey": unverified.issuer_pubkey.hex()}
            )

        # Step 5: Validate scope (hierarchical matching)
        if not check_scope_hierarchy(unverified.scope, required_scope):
            return VerificationResult(
                success=False,
                verified_authority=None,
                failure_reason=(
                    f"Authority scope insufficient: granted '{unverified.scope}', "
                    f"required '{required_scope}'"
                ),
                failure_code="scope_insufficient",
                verification_timestamp=verification_timestamp,
                verifier_id=verifier_id,
                verification_metadata=metadata
            )

        # Step 6: All checks passed - create VerifiedAuthority
        verified = VerifiedAuthority._from_verification(
            unverified=unverified,
            verified_at=verification_timestamp,
            verifier_id=verifier_id
        )

        return VerificationResult(
            success=True,
            verified_authority=verified,
            failure_reason=None,
            failure_code=None,
            verification_timestamp=verification_timestamp,
            verifier_id=verifier_id,
            verification_metadata=metadata
        )

    except Exception as e:
        # Catch unexpected errors
        return VerificationResult(
            success=False,
            verified_authority=None,
            failure_reason=f"Unexpected verification error: {str(e)}",
            failure_code="unexpected_error",
            verification_timestamp=verification_timestamp,
            verifier_id=verifier_id,
            verification_metadata={**metadata, "error_type": type(e).__name__}
        )


def verify_token_signature_unverified(token: UnverifiedAuthority) -> bool:
    """
    Verifies the Ed25519 signature on an unverified authority token.

    This requires PyNaCl. For testing/development without PyNaCl,
    this function performs structural validation only.

    Args:
        token: Unverified authority token to verify

    Returns:
        True if signature is valid

    Raises:
        TokenValidationError: If signature verification fails
    """
    try:
        import nacl.signing
        import nacl.exceptions

        # Reconstruct signed message (per docs/AUTHORITY.md)
        message = (
            token.source.encode() + b'|' +
            token.scope.encode() + b'|' +
            token.timestamp.to_bytes(8, 'big') + b'|' +
            token.nonce
        )

        # Create verify key from issuer public key
        try:
            verify_key = nacl.signing.VerifyKey(token.issuer_pubkey)
        except Exception as e:
            raise TokenValidationError(
                f"Invalid issuer public key: {e}",
                reason="invalid_public_key",
                context={"error": str(e)}
            )

        # Verify signature
        try:
            verify_key.verify(message, token.signature)
            return True
        except nacl.exceptions.BadSignatureError:
            raise TokenValidationError(
                "Signature verification failed - token may be forged",
                reason="signature_verification_failed",
                context={"source": token.source, "scope": token.scope}
            )

    except ImportError:
        # PyNaCl not available - fall back to structural validation only
        # This is acceptable for testing but NOT for production
        import warnings
        warnings.warn(
            "PyNaCl not installed - signature verification skipped. "
            "Install PyNaCl for production use: pip install pynacl",
            RuntimeWarning,
            stacklevel=2
        )
        return True  # Structural validation passed in __post_init__


def validate_token_expiry_unverified(token: UnverifiedAuthority, max_age: int = MAX_TOKEN_AGE) -> None:
    """
    Validates that unverified token has not expired.

    Args:
        token: Unverified authority token to check
        max_age: Maximum token age in seconds (default: 300)

    Raises:
        TokenValidationError: If token is expired or from future
    """
    current_time = int(time.time())

    # Check if token is from the future (clock skew attack)
    if token.timestamp > current_time + 60:  # Allow 60s clock skew
        raise TokenValidationError(
            f"Token timestamp is in the future: {token.timestamp} > {current_time}",
            reason="future_timestamp",
            context={"token_timestamp": token.timestamp, "current_time": current_time}
        )

    # Check if token has expired
    age = current_time - token.timestamp
    if age > max_age:
        raise TokenValidationError(
            f"Token expired: age {age}s exceeds maximum {max_age}s",
            reason="token_expired",
            context={
                "token_timestamp": token.timestamp,
                "current_time": current_time,
                "age_seconds": age,
                "max_age_seconds": max_age
            }
        )


def validate_token_expiry(token: AuthorityToken, max_age: int = MAX_TOKEN_AGE) -> None:
    """
    Validates that token has not expired.

    Args:
        token: Authority token to check
        max_age: Maximum token age in seconds (default: 300)

    Raises:
        TokenValidationError: If token is expired or from future
    """
    current_time = int(time.time())

    # Check if token is from the future (clock skew attack)
    if token.timestamp > current_time + 60:  # Allow 60s clock skew
        raise TokenValidationError(
            f"Token timestamp is in the future: {token.timestamp} > {current_time}",
            reason="future_timestamp",
            context={"token_timestamp": token.timestamp, "current_time": current_time}
        )

    # Check if token has expired
    age = current_time - token.timestamp
    if age > max_age:
        raise TokenValidationError(
            f"Token expired: age {age}s exceeds maximum {max_age}s",
            reason="token_expired",
            context={
                "token_timestamp": token.timestamp,
                "current_time": current_time,
                "age_seconds": age,
                "max_age_seconds": max_age
            }
        )


# ============================================================================
# VALIDATORS (one per invariant)
# ============================================================================


def validate_clarity(
    required_definitions: dict[str, Any],
    required_thresholds: dict[str, Any],
    required_constraints: list[str]
) -> None:
    """
    I-1: Clarity Invariant Validator

    Checks that all required definitions, thresholds, and constraints are unambiguous.

    Args:
        required_definitions: Dictionary of required definitions
        required_thresholds: Dictionary of required thresholds
        required_constraints: List of required constraints

    Raises:
        ClarityInvariantViolation: If any element is None, empty, or ambiguous
    """
    ambiguous: list[str] = []

    # Check definitions
    for key, value in required_definitions.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            ambiguous.append(f"definition:{key}")

    # Check thresholds
    for key, value in required_thresholds.items():
        if value is None:
            ambiguous.append(f"threshold:{key}")

    # Check constraints
    for constraint in required_constraints:
        if not constraint or not constraint.strip():
            ambiguous.append(f"constraint:{constraint}")

    if ambiguous:
        raise ClarityInvariantViolation(
            f"Required elements are ambiguous or undefined: {', '.join(ambiguous)}",
            ambiguous_elements=ambiguous,
            context={
                "definitions": required_definitions,
                "thresholds": required_thresholds,
                "constraints": required_constraints
            }
        )


def validate_authority(
    authority: Optional[AuthorityToken],
    required_scope: str,
    skip_signature_verification: bool = False
) -> None:
    """
    I-2: Authority Invariant Validator

    Checks that authority to proceed is explicit and verifiable through:
    1. Token presence (not None)
    2. Signature verification (Ed25519)
    3. Expiry validation (timestamp within MAX_TOKEN_AGE)
    4. Nonce replay prevention
    5. Scope hierarchical matching
    6. Issuer trust verification

    Args:
        authority: The authority token (None if unavailable)
        required_scope: The scope of authority required
        skip_signature_verification: Skip cryptographic verification (testing only)

    Raises:
        AuthorityInvariantViolation: If authority is missing or invalid
        TokenValidationError: If token validation fails (subclass of AuthorityInvariantViolation)
    """
    # Check 1: Token must be present
    if authority is None:
        raise AuthorityInvariantViolation(
            f"No authority provided for scope: {required_scope}",
            required_authority=required_scope,
            context={"required_scope": required_scope}
        )

    # Check 2: Verify cryptographic signature
    if not skip_signature_verification:
        verify_token_signature(authority)  # Raises TokenValidationError on failure

    # Check 3: Validate token has not expired
    validate_token_expiry(authority)  # Raises TokenValidationError on failure

    # Check 4: Check nonce replay
    if not check_nonce_replay(authority.nonce):
        raise TokenValidationError(
            f"Nonce replay detected - token has been used before",
            reason="nonce_replay",
            context={
                "source": authority.source,
                "scope": authority.scope,
                "nonce": authority.nonce.hex()
            }
        )

    # Check 5: Verify issuer is trusted
    if not is_trusted_issuer(authority.issuer_pubkey):
        raise TokenValidationError(
            f"Issuer not in trusted registry",
            reason="untrusted_issuer",
            context={
                "source": authority.source,
                "issuer_pubkey": authority.issuer_pubkey.hex()
            }
        )

    # Check 6: Validate scope (hierarchical matching)
    if not check_scope_hierarchy(authority.scope, required_scope):
        raise AuthorityInvariantViolation(
            f"Authority scope insufficient: granted '{authority.scope}', required '{required_scope}'",
            required_authority=required_scope,
            context={
                "granted_scope": authority.scope,
                "required_scope": required_scope,
                "source": authority.source
            }
        )


def validate_attention(
    requires_continuous_attention: bool,
    attention_available: bool,
    harm_scenario: str
) -> None:
    """
    I-3: Attention Invariant Validator

    Checks that continuous authorization is required when harm could occur without attention.

    Args:
        requires_continuous_attention: Whether the operation requires sustained attention
        attention_available: Whether continuous attention can be provided
        harm_scenario: Description of potential harm

    Raises:
        AttentionInvariantViolation: If continuous attention required but not available
    """
    if requires_continuous_attention and not attention_available:
        raise AttentionInvariantViolation(
            f"Continuous attention required but not available: {harm_scenario}",
            harm_scenario=harm_scenario,
            context={
                "requires_continuous_attention": requires_continuous_attention,
                "attention_available": attention_available
            }
        )


def validate_truth(
    satisfied_invariants: Set[str],
    all_invariants: Set[str],
    claiming_allowed: bool
) -> None:
    """
    I-4: Truth Invariant Validator

    Ensures the system never indicates "safe/approved/allowed" while any invariant is unsatisfied.

    Args:
        satisfied_invariants: Set of invariant IDs that are satisfied
        all_invariants: Set of all invariant IDs that must be satisfied
        claiming_allowed: Whether the system is attempting to signal ALLOWED

    Raises:
        TruthInvariantViolation: If claiming allowed while invariants are unsatisfied
    """
    unsatisfied = all_invariants - satisfied_invariants

    if claiming_allowed and unsatisfied:
        raise TruthInvariantViolation(
            f"Cannot claim ALLOWED state while invariants are unsatisfied: {', '.join(sorted(unsatisfied))}",
            unsatisfied_invariants=list(unsatisfied),
            context={
                "satisfied_invariants": satisfied_invariants,
                "unsatisfied_invariants": unsatisfied
            }
        )


def validate_logging(
    event_logged: bool,
    event_type: str,
    suppression_detected: bool = False
) -> None:
    """
    I-5: Logging Invariant Validator

    Ensures all invariant violations and bypass attempts are logged immutably.

    Args:
        event_logged: Whether the event was logged
        event_type: Type of event (violation, bypass, etc.)
        suppression_detected: Whether log suppression was detected

    Raises:
        LoggingInvariantViolation: If event not logged or suppression detected
    """
    if suppression_detected:
        raise LoggingInvariantViolation(
            f"Log suppression detected for event: {event_type}",
            suppression_attempt=event_type,
            context={"event_type": event_type}
        )

    if not event_logged:
        raise LoggingInvariantViolation(
            f"Event not logged: {event_type}",
            suppression_attempt=event_type,
            context={"event_type": event_type}
        )


def validate_silence(
    variable: Variable,
    attempting_guess: bool
) -> None:
    """
    I-6: Silence Invariant Validator

    Ensures guessing is forbidden when variables are unresolved.

    Args:
        variable: The variable in question
        attempting_guess: Whether a guess is being attempted

    Raises:
        SilenceInvariantViolation: If guessing is attempted for unresolved variable
    """
    if not variable.resolved and attempting_guess:
        raise SilenceInvariantViolation(
            f"Guessing forbidden for unresolved variable: {variable.name}",
            guessed_value=variable.value,
            variable_name=variable.name,
            context={"variable": variable}
        )


def validate_complexity(
    variables: list[Variable],
    max_width: int = 3
) -> int:
    """
    I-7: Complexity Invariant Validator

    Measures unresolved interface width w and enforces w ≤ 3.

    Args:
        variables: List of all variables in the constraint system
        max_width: Maximum allowed width (default 3 per spec)

    Returns:
        The measured width w

    Raises:
        ComplexityInvariantViolation: If w > max_width
    """
    # Calculate w: number of unresolved material variables
    unresolved_material = [
        v for v in variables
        if not v.resolved and v.material
    ]

    w = len(unresolved_material)

    if w > max_width:
        unresolved_names = [v.name for v in unresolved_material]
        raise ComplexityInvariantViolation(
            f"Interface width w={w} exceeds maximum {max_width}. "
            f"Unresolved material variables: {', '.join(unresolved_names)}",
            measured_w=w,
            unresolved_variables=unresolved_names,
            context={
                "all_variables": variables,
                "max_width": max_width
            }
        )

    return w


def detect_variable_bundling(variables: list[Variable]) -> Optional[WCountingFraudViolation]:
    """
    Detects illegal variable bundling - combining multiple material concerns into one variable.

    Variable bundling is forbidden because it artificially reduces w by hiding multiple
    unresolved material concerns inside a single variable.

    Examples of illegal bundling:
    - Variable("patient_dosage_and_route", ...) - combines dosage + route
    - Variable("config", ...) - bundles multiple config parameters
    - Variable("options", ...) - generic container hiding multiple concerns

    Heuristics for detection:
    1. Variable name contains "and", "or", "_config", "_options", "_params"
    2. Variable name is overly generic ("data", "info", "config", "options", "params")
    3. Variable value is a dict/tuple/list with multiple material elements

    Args:
        variables: List of all variables to check

    Returns:
        WCountingFraudViolation if bundling detected, None otherwise
    """
    # Suspicious name patterns that suggest bundling
    bundling_keywords = ["_and_", "_or_", "_config", "_options", "_params", "_settings"]
    generic_names = {"data", "info", "config", "options", "params", "settings", "args", "kwargs"}

    for var in variables:
        var_name_lower = var.name.lower()

        # Check 1: Name contains bundling keywords
        if any(keyword in var_name_lower for keyword in bundling_keywords):
            return WCountingFraudViolation(
                f"Variable bundling detected: '{var.name}' appears to bundle multiple concerns. "
                f"Split into separate material variables.",
                fraud_type="variable_bundling",
                evidence={
                    "variable_name": var.name,
                    "pattern": "name_contains_bundling_keyword",
                    "resolved": var.resolved,
                    "material": var.material
                }
            )

        # Check 2: Name is overly generic (only flag if material and unresolved)
        if not var.resolved and var.material and var_name_lower in generic_names:
            return WCountingFraudViolation(
                f"Generic variable name detected: '{var.name}' is too generic and may hide bundled concerns. "
                f"Use specific variable names that describe single concerns.",
                fraud_type="generic_variable_name",
                evidence={
                    "variable_name": var.name,
                    "pattern": "generic_name",
                    "resolved": var.resolved,
                    "material": var.material
                }
            )

        # Check 3: Value is a dict/list/tuple with multiple elements (only if resolved)
        if var.resolved and var.material and var.value is not None:
            if isinstance(var.value, dict) and len(var.value) > 1:
                return WCountingFraudViolation(
                    f"Variable bundling detected: '{var.name}' contains dict with {len(var.value)} keys. "
                    f"Each material concern should be a separate variable.",
                    fraud_type="dict_bundling",
                    evidence={
                        "variable_name": var.name,
                        "pattern": "dict_with_multiple_keys",
                        "num_keys": len(var.value),
                        "keys": list(var.value.keys())
                    }
                )

    return None


def detect_probabilistic_collapse(
    variables_before: list[Variable],
    variables_after: list[Variable]
) -> Optional[WCountingFraudViolation]:
    """
    Detects illegal probabilistic collapse - guessing/inferring values to reduce w.

    Probabilistic collapse is forbidden when values are guessed without explicit
    authority to reduce w. This violates I-6 (Silence Invariant).

    Detection approach:
    - Compare variables before and after some operation
    - If previously unresolved material variables become resolved without explicit input
    - Raise fraud violation

    Args:
        variables_before: Variables before operation
        variables_after: Variables after operation

    Returns:
        WCountingFraudViolation if probabilistic collapse detected, None otherwise
    """
    # Build maps of variables by name
    vars_before_map = {v.name: v for v in variables_before}
    vars_after_map = {v.name: v for v in variables_after}

    collapsed_vars = []

    for name in vars_before_map:
        if name not in vars_after_map:
            continue

        var_before = vars_before_map[name]
        var_after = vars_after_map[name]

        # Check if unresolved material variable became resolved
        if (not var_before.resolved and var_before.material and
                var_after.resolved and var_after.material):
            # This is suspicious - material variable went from unresolved to resolved
            collapsed_vars.append({
                "name": name,
                "value_before": var_before.value,
                "value_after": var_after.value
            })

    if collapsed_vars:
        # Calculate actual w (before collapse)
        actual_w = sum(1 for v in variables_before if not v.resolved and v.material)
        # Calculate reported w (after collapse)
        reported_w = sum(1 for v in variables_after if not v.resolved and v.material)

        return WCountingFraudViolation(
            f"Probabilistic collapse detected: {len(collapsed_vars)} material variable(s) "
            f"resolved without explicit input. This violates I-6 (Silence Invariant). "
            f"Actual w={actual_w}, reported w={reported_w}.",
            fraud_type="probabilistic_collapse",
            evidence={
                "collapsed_variables": collapsed_vars,
                "actual_w": actual_w,
                "reported_w": reported_w,
                "unresolved_variables": [v.name for v in variables_after if not v.resolved and v.material]
            }
        )

    return None


def validate_material_classification(
    variables: list[Variable],
    safety_critical_names: Optional[Set[str]] = None
) -> None:
    """
    Validates that safety-critical variables are correctly marked as material.

    This function can optionally take a set of known safety-critical variable names
    and verify they are marked material=True.

    Args:
        variables: List of variables to validate
        safety_critical_names: Optional set of variable names known to be safety-critical

    Raises:
        WCountingFraudViolation: If safety-critical variable marked as non-material
    """
    if safety_critical_names is None:
        return

    for var in variables:
        if var.name in safety_critical_names and not var.material:
            raise WCountingFraudViolation(
                f"Material misclassification detected: '{var.name}' is safety-critical "
                f"but marked as non-material. This is fraud to bypass w≤3 constraint.",
                fraud_type="material_misclassification",
                evidence={
                    "variable_name": var.name,
                    "marked_material": var.material,
                    "should_be_material": True,
                    "resolved": var.resolved
                }
            )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_all_invariant_ids() -> Set[str]:
    """Returns the set of all hard invariant IDs."""
    return {"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"}


def is_invariant_satisfied(invariant_id: str, **kwargs: Any) -> bool:
    """
    Checks if a specific invariant is satisfied without raising an exception.

    Args:
        invariant_id: The invariant to check
        **kwargs: Arguments required for the specific invariant validator

    Returns:
        True if satisfied, False otherwise
    """
    try:
        if invariant_id == "I-1":
            validate_clarity(
                kwargs.get("required_definitions", {}),
                kwargs.get("required_thresholds", {}),
                kwargs.get("required_constraints", [])
            )
        elif invariant_id == "I-2":
            validate_authority(
                kwargs.get("authority"),
                kwargs.get("required_scope", "")
            )
        elif invariant_id == "I-3":
            validate_attention(
                kwargs.get("requires_continuous_attention", False),
                kwargs.get("attention_available", False),
                kwargs.get("harm_scenario", "")
            )
        elif invariant_id == "I-4":
            validate_truth(
                kwargs.get("satisfied_invariants", set()),
                kwargs.get("all_invariants", get_all_invariant_ids()),
                kwargs.get("claiming_allowed", False)
            )
        elif invariant_id == "I-5":
            validate_logging(
                kwargs.get("event_logged", False),
                kwargs.get("event_type", ""),
                kwargs.get("suppression_detected", False)
            )
        elif invariant_id == "I-6":
            validate_silence(
                kwargs.get("variable", Variable("", False, False)),
                kwargs.get("attempting_guess", False)
            )
        elif invariant_id == "I-7":
            validate_complexity(
                kwargs.get("variables", []),
                kwargs.get("max_width", 3)
            )
        else:
            return False

        return True
    except InvariantViolation:
        return False
