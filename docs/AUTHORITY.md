# Authority Specification
## Cryptographic Verification and Token Issuance

**Version:** 1.0
**Framework Version:** Clarity Kernel v1.2.0
**Status:** Normative Specification

---

## Purpose

This document specifies the **authority verification mechanism** required by Invariant I-2 (Authority).

The Clarity Kernel enforces that operations cannot proceed without **explicit, verifiable authority**. This specification defines what constitutes "verifiable" authority and how tokens must be validated.

---

## Core Principle

**Authority ≠ Capability**

The fact that an entity *can* perform an operation does not mean it *should*. The kernel enforces separation between:
- **Capability:** Technical ability to execute
- **Authority:** Explicit permission to execute

---

## Authority Token Structure

### Required Fields

```python
@dataclass
class AuthorityToken:
    source: str           # Identity of authorizing entity
    verifiable: bool      # DEPRECATED - See verification section
    scope: str            # Scope of authorization
    signature: bytes      # Cryptographic signature (Ed25519)
    timestamp: int        # Unix timestamp of issuance
    nonce: bytes          # Random nonce (32 bytes)
    issuer_pubkey: bytes  # Public key of issuer (32 bytes)
```

### Field Specifications

**source (str)**
- Human-readable identifier of the authorizing entity
- Examples: `"admin_alice"`, `"security_team"`, `"doctor_smith"`
- Must not be empty
- Must not contain null bytes

**scope (str)**
- Hierarchical scope identifier using dot notation
- Examples: `"file.read"`, `"medical.prescribe"`, `"financial.transfer"`
- Scope hierarchy: `"medical.prescribe"` ⊆ `"medical.*"` ⊆ `"*"`
- Must match `required_scope` in PermissionRequest

**signature (bytes)**
- Ed25519 signature (64 bytes)
- Signs the concatenation: `source || scope || timestamp || nonce`
- Verified against `issuer_pubkey`

**timestamp (int)**
- Unix timestamp (seconds since epoch) of token issuance
- Must not be in the future
- Must not be older than max_age (default: 300 seconds)

**nonce (bytes)**
- Random 32-byte nonce (cryptographically secure random)
- Prevents replay attacks
- Must be unique per token

**issuer_pubkey (bytes)**
- Ed25519 public key (32 bytes) of the trusted authority issuer
- Must be registered in trusted issuer registry
- Corresponds to private key used to sign token

---

## Verification Mechanism

### I-2 (Authority Invariant) - Formal Verification

An AuthorityToken satisfies I-2 if and only if:

```
I-2 := authority_token ≠ NULL
      ∧ authority_token.signature ≠ NULL
      ∧ verify_signature(authority_token) = TRUE
      ∧ verify_timestamp(authority_token) = TRUE
      ∧ verify_scope(authority_token, required_scope) = TRUE
      ∧ verify_issuer(authority_token) = TRUE
```

### Verification Algorithm

```python
def verify_authority_token(token: AuthorityToken, required_scope: str) -> bool:
    # Step 1: Signature verification
    message = token.source.encode() + b'|' + \
              token.scope.encode() + b'|' + \
              token.timestamp.to_bytes(8, 'big') + b'|' + \
              token.nonce

    if not ed25519_verify(token.signature, message, token.issuer_pubkey):
        return False  # Invalid signature

    # Step 2: Timestamp verification
    current_time = int(time.time())
    if token.timestamp > current_time:
        return False  # Token from future (clock skew attack)

    if current_time - token.timestamp > MAX_TOKEN_AGE:
        return False  # Expired token

    # Step 3: Scope verification
    if not scope_matches(token.scope, required_scope):
        return False  # Insufficient scope

    # Step 4: Issuer verification
    if token.issuer_pubkey not in TRUSTED_ISSUER_REGISTRY:
        return False  # Untrusted issuer

    return True
```

### Scope Matching Rules

```python
def scope_matches(granted_scope: str, required_scope: str) -> bool:
    # Exact match
    if granted_scope == required_scope:
        return True

    # Wildcard match (granted "medical.*" covers required "medical.prescribe")
    if granted_scope.endswith(".*"):
        prefix = granted_scope[:-2]
        if required_scope.startswith(prefix + "."):
            return True

    # Universal wildcard
    if granted_scope == "*":
        return True

    return False
```

---

## Token Issuance Process

### Step 1: Authority Server

A **trusted authority server** issues tokens. This server:
- Holds Ed25519 private keys corresponding to registered public keys
- Authenticates requesters (human or system)
- Determines appropriate scope for each request
- Signs tokens with private key

### Step 2: Authentication

Before issuing token, authority server must:
1. Authenticate requester identity (password, certificate, biometric, etc.)
2. Verify requester is authorized to receive token for requested scope
3. Log issuance event for audit

### Step 3: Token Generation

```python
def issue_token(source: str, scope: str, private_key: bytes) -> AuthorityToken:
    timestamp = int(time.time())
    nonce = os.urandom(32)

    message = source.encode() + b'|' + \
              scope.encode() + b'|' + \
              timestamp.to_bytes(8, 'big') + b'|' + \
              nonce

    signature = ed25519_sign(message, private_key)
    public_key = ed25519_public_key(private_key)

    return AuthorityToken(
        source=source,
        verifiable=True,  # DEPRECATED field, always True for signed tokens
        scope=scope,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
        issuer_pubkey=public_key
    )
```

### Step 4: Token Distribution

Token is returned to requester via secure channel (TLS, encrypted message, etc.)

---

## Trusted Issuer Registry

### Registry Structure

The kernel maintains (or references) a **trusted issuer registry**:

```python
TRUSTED_ISSUER_REGISTRY = {
    bytes.fromhex("a1b2c3..."): {
        "name": "primary_authority_server",
        "added": 1704067200,
        "max_scope": "*"
    },
    bytes.fromhex("d4e5f6..."): {
        "name": "medical_authority_server",
        "added": 1704067200,
        "max_scope": "medical.*"
    }
}
```

### Registry Management

**Adding issuer:**
- Requires administrative action (out-of-band)
- Public key must be verified via secure channel
- Scope constraints enforced (issuer cannot grant scopes beyond max_scope)

**Removing issuer:**
- All tokens signed by that issuer become invalid immediately
- Requires administrative action
- Logged for audit

---

## Security Properties

### Properties Enforced

1. **Non-forgery:** Attacker cannot create valid token without private key
2. **Non-replay:** Each token usable only once (nonce tracking required)
3. **Non-expiry-bypass:** Expired tokens cannot be used
4. **Non-scope-escalation:** Token cannot be used for higher-privilege scope
5. **Non-issuer-impersonation:** Only tokens from trusted issuers accepted

### Attack Resistance

**Token theft:**
- Tokens are single-use (nonce prevents replay)
- Short lifetime (default 300s) limits exposure window

**Clock skew attacks:**
- Future-dated tokens rejected
- Server time used for verification (not client time)

**Scope escalation:**
- Scope hierarchy enforced in verification
- Cannot use `"medical.read"` token for `"medical.prescribe"`

---

## Implementation Requirements

### Kernel Implementation

The kernel MUST:
1. Verify signature before accepting authority token
2. Check timestamp is within acceptable range
3. Verify scope matches or exceeds required scope
4. Verify issuer public key is in trusted registry
5. Log all verification failures with reason codes

### Application Implementation

Applications MUST:
1. Obtain tokens from trusted authority server
2. Include token in every PermissionRequest
3. Not cache tokens beyond expiry time
4. Not share tokens between operations (single-use principle)
5. Handle token expiry gracefully (request new token)

---

## Compliance Checklist

Before deploying Clarity Kernel in production:

- [ ] Authority server implemented and deployed
- [ ] Ed25519 key pair generated for authority server
- [ ] Public key registered in kernel's trusted issuer registry
- [ ] Token issuance workflow implemented (authentication + signing)
- [ ] Token distribution channel secured (TLS/encryption)
- [ ] Kernel configured with trusted issuer registry
- [ ] Verification logic tested with valid and invalid tokens
- [ ] Token expiry handling implemented in application
- [ ] Audit logging configured for all issuance and verification events

---

## Reference Implementation

See `examples/02_authority_token.py` for complete example of:
- Token generation (authority server side)
- Token verification (kernel side)
- Token usage (application side)

---

## Constants

```python
# Token lifetime (seconds)
MAX_TOKEN_AGE = 300  # 5 minutes

# Signature algorithm
SIGNATURE_ALGORITHM = "Ed25519"

# Signature length
SIGNATURE_LENGTH = 64  # bytes

# Public key length
PUBKEY_LENGTH = 32  # bytes

# Nonce length
NONCE_LENGTH = 32  # bytes
```

---

## Deprecation Notice

**DEPRECATED: `verifiable: bool` field**

Older versions of AuthorityToken used a boolean `verifiable` flag. This is DEPRECATED.

The presence of a valid `signature` field is the ONLY indicator of verifiability.

Legacy code checking `if authority.verifiable:` should be replaced with proper signature verification.

---

**End of Authority Specification**
