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
class AuthorityToken:
    """
    Represents an explicit, cryptographically-verified authorization.

    This is a security-critical object. All fields must be present for production use.
    See docs/AUTHORITY.md for complete specification.

    Security Properties:
    - Ed25519 signature prevents forgery
    - Timestamp prevents replay of expired tokens
    - Nonce prevents replay of valid tokens
    - Scope limits authorization domain
    - Issuer public key enables verification

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
