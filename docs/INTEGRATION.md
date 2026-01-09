# Integration Guide
## Step-by-Step Tutorial for Clarity Kernel Integration

**Version:** 1.0
**Framework Version:** Clarity Kernel v1.2.0
**Status:** Normative Guide

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Authority Setup](#authority-setup)
4. [Variable Classification](#variable-classification)
5. [Control Mode Selection](#control-mode-selection)
6. [Error Handling](#error-handling)
7. [Logging Configuration](#logging-configuration)
8. [Production Deployment](#production-deployment)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)

---

## Installation

### Step 1: Install the Package

```bash
pip install clarity-kernel
```

### Step 2: Verify Installation

```python
import clarity_kernel
print(clarity_kernel.__version__)  # Should print "1.2.0"
```

### Step 3: Import Core Components

```python
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
)
```

---

## Quick Start

### Simplest Possible Integration

```python
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
)

# Step 1: Create kernel instance
kernel = ClarityKernel()

# Step 2: Create authority token (see Authority Setup for production)
authority = AuthorityToken(
    source="admin_alice",
    verifiable=True,
    scope="file.read",
    signature=b'\x00' * 64,  # PLACEHOLDER - use real signature in production
    timestamp=int(time.time()),
    nonce=os.urandom(32),
    issuer_pubkey=b'\x00' * 32  # PLACEHOLDER - use real pubkey in production
)

# Step 3: Define variables
variables = [
    Variable(
        name="file_path",
        resolved=True,
        material=True,
        value="/etc/config.yaml"
    )
]

# Step 4: Build permission request
request = PermissionRequest(
    operation_id="read_config_001",
    variables=variables,
    required_definitions={"file_path": "/etc/config.yaml"},
    required_thresholds={},
    required_constraints=["file_exists", "read_permission"],
    authority=authority,
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

# Step 5: Request permission
try:
    response = kernel.request_permission(request)

    if response.granted:
        print(f"✓ Permission granted (mode: {response.control_mode.value})")
        print(f"  Interface width w={response.measured_w}")
        print(f"  Satisfied invariants: {response.satisfied_invariants}")

        # Execute your operation here
        with open("/etc/config.yaml", "r") as f:
            config = f.read()

except PermissionDenied as e:
    print(f"✗ Permission denied: {e.reason}")
    print(f"  Kernel state: {e.kernel_state}")
```

---

## Authority Setup

### Production Authority Token Generation

**DO NOT use placeholder signatures in production.**

The Clarity Kernel requires cryptographically verifiable authority tokens using Ed25519 signatures.

### Step 1: Generate Authority Server Keys

```python
import nacl.signing
import nacl.encoding

# Generate Ed25519 key pair (do this ONCE, store securely)
signing_key = nacl.signing.SigningKey.generate()
verify_key = signing_key.verify_key

# Save keys securely
with open("authority_private.key", "wb") as f:
    f.write(signing_key.encode())

with open("authority_public.key", "wb") as f:
    f.write(verify_key.encode())

print(f"Public key (register in kernel): {verify_key.encode().hex()}")
```

### Step 2: Implement Token Issuance Endpoint

```python
import time
import os
import nacl.signing

def issue_authority_token(
    source: str,
    scope: str,
    private_key_path: str
) -> AuthorityToken:
    """
    Issues a signed authority token.

    This function should run on a trusted authority server with:
    - User authentication
    - Authorization policy checks
    - Audit logging
    """
    # Load private key
    with open(private_key_path, "rb") as f:
        signing_key = nacl.signing.SigningKey(f.read())

    # Generate token fields
    timestamp = int(time.time())
    nonce = os.urandom(32)

    # Construct message to sign
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

    return AuthorityToken(
        source=source,
        verifiable=True,
        scope=scope,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
        issuer_pubkey=public_key
    )

# Example usage
token = issue_authority_token(
    source="admin_alice",
    scope="file.read",
    private_key_path="authority_private.key"
)
```

### Step 3: Register Public Key in Kernel

```python
# In your kernel initialization code
TRUSTED_ISSUER_REGISTRY = {
    bytes.fromhex("a1b2c3..."): {  # Replace with actual public key
        "name": "primary_authority_server",
        "added": 1704067200,
        "max_scope": "*"
    }
}
```

**See docs/AUTHORITY.md for complete authority specification.**

---

## Variable Classification

### Decision Process

**Before adding a variable to your PermissionRequest, classify it as material or non-material.**

Use this decision tree from docs/VARIABLES.md:

```
Is the variable's value required for the operation to be:
  - Safe?           YES → MATERIAL
  - Correct?        YES → MATERIAL
  - Authorized?     YES → MATERIAL

Does the variable's value determine:
  - Execution path? YES → MATERIAL
  - Safety margin?  YES → MATERIAL

Does the variable's absence cause:
  - Undefined behavior? YES → MATERIAL
  - Incorrect result?   YES → MATERIAL

Does the variable have:
  - A safe default that preserves correctness? NO → MATERIAL

Is the variable used ONLY for:
  - Logging?        YES → NON-MATERIAL
  - Telemetry?      YES → NON-MATERIAL
  - Optimization?   YES (if correctness preserved) → NON-MATERIAL

DEFAULT: When in doubt → MATERIAL
```

### Example: File Read Operation

```python
variables = [
    # MATERIAL: Determines which file to access (correctness-critical)
    Variable(
        name="file_path",
        resolved=True,
        material=True,
        value="/etc/config.yaml"
    ),

    # MATERIAL: Determines read mode (correctness-affecting)
    Variable(
        name="read_mode",
        resolved=True,
        material=True,
        value="text"
    ),

    # NON-MATERIAL: Used only for logging, has safe default (empty string)
    Variable(
        name="request_id",
        resolved=True,
        material=False,
        value="req_12345"
    ),

    # NON-MATERIAL: Performance hint, does not affect correctness
    Variable(
        name="use_cache",
        resolved=True,
        material=False,
        value=True
    )
]

# Measured w = 0 (no unresolved material variables)
```

### Example: Medical Dosage Calculation

```python
variables = [
    # MATERIAL: Determines dosage (safety-critical)
    Variable(
        name="dosage_mg",
        resolved=False,  # Unresolved - needs human input
        material=True,
        value=None
    ),

    # MATERIAL: Determines safety threshold (safety-critical)
    Variable(
        name="patient_weight_kg",
        resolved=True,
        material=True,
        value=70.5
    ),

    # MATERIAL: Affects drug interaction safety (safety-critical)
    Variable(
        name="concurrent_medications",
        resolved=True,
        material=True,
        value=["aspirin", "lisinopril"]
    ),

    # NON-MATERIAL: Used only for telemetry
    Variable(
        name="prescriber_id",
        resolved=True,
        material=False,
        value="DR_SMITH_12345"
    )
]

# Measured w = 1 (dosage_mg is unresolved and material)
```

**CRITICAL:** Do not mark safety-critical variables as non-material to game the w≤3 limit. This undermines the entire safety guarantee.

---

## Control Mode Selection

### Decision Matrix

**Use this matrix to determine preconditions and triggers:**

| Operation Characteristic | Momentary Precondition | Continuous Trigger |
|-------------------------|------------------------|-------------------|
| Outcome can be undone | outcome_reversible=True | outcome_irreversible=False |
| Outcome permanent | outcome_reversible=False | outcome_irreversible=True |
| Risk constant | risk_does_not_increase=True | (not applicable) |
| Risk increases over time | risk_does_not_increase=False | (not applicable) |
| No new critical info | no_new_critical_info=True | context_may_change=False |
| Critical info may emerge | no_new_critical_info=False | context_may_change=True |
| w stable at start | w_within_limit=True | w_may_fluctuate=False |
| w may change | w_within_limit=False | w_may_fluctuate=True |
| Execution < 1 minute | execution_window_bounded=True | execution_window_extended=False |
| Execution ≥ 1 minute | execution_window_bounded=False | execution_window_extended=True |
| Compliance/safety concern | (not applicable) | compliance_safety_exposure=True |
| Ambiguity at start | (not applicable) | ambiguity_at_initiation=True |

### Example: File Delete (Momentary)

```python
# Irreversible operation → Should use continuous mode OR
# If trash/recycle available → Can use momentary mode

preconditions = MomentaryPreconditions(
    outcome_reversible=True,  # Can restore from trash
    risk_does_not_increase=True,  # Risk constant
    no_new_critical_info=True,  # No new info expected
    w_within_limit=True,  # w=0
    execution_window_bounded=True  # Instant delete
)

triggers = ContinuousTriggers(
    outcome_irreversible=False,  # Recoverable from trash
    compliance_safety_exposure=False,
    context_may_change=False,
    ambiguity_at_initiation=False,
    w_may_fluctuate=False,
    execution_window_extended=False
)

# Result: MOMENTARY mode
```

### Example: Financial Transfer (Continuous)

```python
# Irreversible, high-value operation → MUST use continuous mode

preconditions = MomentaryPreconditions(
    outcome_reversible=False,  # Cannot undo transfer
    risk_does_not_increase=False,  # Risk increases if context changes
    no_new_critical_info=False,  # Fraud alerts may emerge
    w_within_limit=True,  # w=0
    execution_window_bounded=False  # Network delays possible
)

triggers = ContinuousTriggers(
    outcome_irreversible=True,  # TRIGGER: Permanent transfer
    compliance_safety_exposure=True,  # TRIGGER: Regulatory concern
    context_may_change=True,  # TRIGGER: Fraud detection
    ambiguity_at_initiation=False,
    w_may_fluctuate=False,
    execution_window_extended=True  # TRIGGER: May take time
)

# Result: CONTINUOUS mode (multiple triggers)
```

### Using Continuous Mode Execution Guard

```python
response = kernel.request_permission(request)

if response.control_mode == ControlMode.CONTINUOUS:
    guard = response.execution_guard  # ContinuousExecutionGuard

    # Execute with periodic confirmation checks
    for step in operation_steps:
        # Check if authorization still valid
        if not guard.check_confirmation():
            # Authorization lost - immediate stop
            kernel.trigger_immediate_stop(
                reason="Continuous authorization lost",
                triggered_by="execution_loop"
            )

        # Execute step
        execute_step(step)

        # Confirm still authorized
        guard.confirm()
```

---

## Error Handling

### Standard Error Handling Pattern

```python
from clarity_kernel import (
    PermissionDenied,
    ImmediateStopTriggered,
    InvariantViolation,
    ClarityInvariantViolation,
    AuthorityInvariantViolation,
    ComplexityInvariantViolation,
)

try:
    response = kernel.request_permission(request)

    # Execute operation
    result = execute_operation()

except ClarityInvariantViolation as e:
    # I-1 violated: Ambiguous definitions/thresholds
    print(f"Ambiguity detected: {e.ambiguous_elements}")
    # Option 1: Resolve ambiguity and retry
    # Option 2: Decompose operation into clearer sub-operations
    # Option 3: Request human clarification

except AuthorityInvariantViolation as e:
    # I-2 violated: No valid authority
    print(f"Authority required: {e.required_authority}")
    # Option 1: Obtain authority token from authority server
    # Option 2: Request human authorization

except ComplexityInvariantViolation as e:
    # I-7 violated: w > 3
    print(f"Interface too wide: w={e.measured_w}")
    print(f"Unresolved variables: {e.unresolved_variables}")
    # Option 1: Resolve some variables to reduce w
    # Option 2: Decompose operation into smaller sub-operations
    # Option 3: Apply override (if justified)

except PermissionDenied as e:
    # Generic denial
    print(f"Denied: {e.reason}")
    print(f"State: {e.kernel_state}")
    # Log denial and handle gracefully

except ImmediateStopTriggered as e:
    # Immediate stop - halt all execution
    print(f"STOP: {e.trigger}")
    # Graceful shutdown, no retry
```

### Specific Invariant Handling

**See docs/ERROR_HANDLING.md for complete exception reference.**

---

## Logging Configuration

### Default Logger

```python
from clarity_kernel import get_default_logger

logger = get_default_logger()
kernel = ClarityKernel(logger=logger)
```

### Custom Logger

```python
from clarity_kernel import AuditLogger
import json

class CustomAuditLogger(AuditLogger):
    def __init__(self, output_file: str):
        super().__init__()
        self.output_file = output_file

    def _write_log(self, entry: dict) -> None:
        with open(self.output_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

# Use custom logger
logger = CustomAuditLogger("audit.jsonl")
kernel = ClarityKernel(logger=logger)
```

### Structured Logging Integration

```python
import structlog

class StructlogAuditLogger(AuditLogger):
    def __init__(self):
        super().__init__()
        self.log = structlog.get_logger()

    def log_authorization(self, granted, authority_source, required_scope,
                         kernel_state, control_mode, context=None):
        self.log.info(
            "authorization",
            granted=granted,
            authority_source=authority_source,
            required_scope=required_scope,
            kernel_state=kernel_state,
            control_mode=control_mode,
            **(context or {})
        )
```

---

## Production Deployment

### Pre-Deployment Checklist

Before deploying Clarity Kernel to production:

#### Authority Configuration

- [ ] Ed25519 key pair generated for authority server
- [ ] Private key stored securely (HSM, vault, encrypted storage)
- [ ] Public key registered in kernel's trusted issuer registry
- [ ] Token issuance endpoint implemented with authentication
- [ ] Token distribution channel secured (TLS, encryption)
- [ ] Token expiry handling implemented (default 300s lifetime)

#### Variable Classification

- [ ] All variables classified as material or non-material
- [ ] Each non-material classification has written justification
- [ ] Material classification reviewed for safety-critical operations
- [ ] No gaming of w≤3 through misclassification

#### Control Mode Configuration

- [ ] Preconditions reviewed for all momentary operations
- [ ] Triggers reviewed for all continuous operations
- [ ] Continuous mode confirmation mechanism implemented
- [ ] Deadman switch behavior tested

#### Logging

- [ ] Audit logging configured with immutable storage
- [ ] Log retention policy established
- [ ] Log review process established
- [ ] Alert rules configured for invariant violations

#### Error Handling

- [ ] All exception types handled gracefully
- [ ] Invariant violations logged for review
- [ ] Retry logic avoids infinite loops
- [ ] Immediate stop handling tested

#### Testing

- [ ] Unit tests for all PermissionRequest constructions
- [ ] Integration tests for control mode transitions
- [ ] Chaos tests for invariant violations
- [ ] Load tests for authority token verification

---

## Common Patterns

### Pattern 1: Simple Read Operation

```python
def read_file_with_kernel(file_path: str, authority: AuthorityToken) -> str:
    kernel = ClarityKernel()

    request = PermissionRequest(
        operation_id=f"read_file_{uuid.uuid4()}",
        variables=[
            Variable("file_path", resolved=True, material=True, value=file_path)
        ],
        required_definitions={"file_path": file_path},
        required_thresholds={},
        required_constraints=["file_exists", "read_permission"],
        authority=authority,
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

    response = kernel.request_permission(request)

    if response.granted:
        with open(file_path, "r") as f:
            return f.read()
    else:
        raise PermissionDenied(
            "File read denied",
            reason=response.denial_reason,
            kernel_state=response.kernel_state.value
        )
```

### Pattern 2: Handling w > 3

```python
def handle_width_violation(operation_id: str, variables: list[Variable]):
    """
    When w > 3, decompose operation or resolve variables.
    """
    # Calculate w
    w = sum(1 for v in variables if not v.resolved and v.material)

    if w <= 3:
        # Proceed normally
        return create_permission_request(operation_id, variables)

    # Option 1: Resolve some variables
    print(f"Interface width w={w} exceeds limit. Resolving variables...")
    for var in variables:
        if not var.resolved and var.material:
            # Prompt user for value
            value = input(f"Please provide value for {var.name}: ")
            # Create new resolved variable
            var = Variable(var.name, resolved=True, material=True, value=value)

    # Option 2: Decompose into sub-operations
    # Split operation into smaller operations with w ≤ 3 each

    # Option 3: Apply override (if justified)
    # kernel.apply_override(...)
```

### Pattern 3: Continuous Authorization Loop

```python
def long_running_operation_with_continuous_auth(
    authority: AuthorityToken,
    confirm_callback: Callable[[], bool]
) -> None:
    kernel = ClarityKernel()

    request = PermissionRequest(
        operation_id=f"long_running_{uuid.uuid4()}",
        # ... other fields ...
        triggers=ContinuousTriggers(
            outcome_irreversible=True,
            compliance_safety_exposure=True,
            context_may_change=True,
            ambiguity_at_initiation=False,
            w_may_fluctuate=False,
            execution_window_extended=True  # Long operation
        ),
        requires_continuous_attention=True,
        harm_scenario="Operation cannot be undone if stopped mid-execution"
    )

    response = kernel.request_permission(request)

    if response.control_mode == ControlMode.CONTINUOUS:
        guard = response.execution_guard

        for step in operation_steps:
            # Check confirmation
            if not confirm_callback():
                kernel.trigger_immediate_stop(
                    reason="User confirmation lost",
                    triggered_by="confirm_callback"
                )

            # Execute step
            execute_step(step)

            # Confirm still authorized
            guard.confirm()
```

---

## Troubleshooting

### Problem: PermissionDenied with "Clarity invariant violated"

**Cause:** Ambiguous definitions, thresholds, or constraints.

**Solution:**
1. Check `required_definitions` - ensure all values are concrete, not ambiguous
2. Check `required_thresholds` - ensure all thresholds are numeric
3. Check `required_constraints` - ensure all constraints explicitly stated

### Problem: PermissionDenied with "Authority invariant violated"

**Cause:** Missing or invalid authority token.

**Solution:**
1. Ensure `authority` is not None
2. Verify signature is valid (64 bytes Ed25519 signature)
3. Check timestamp is not expired (default 300s lifetime)
4. Verify scope matches or exceeds required_scope
5. Confirm issuer public key is in trusted registry

### Problem: PermissionDenied with "Complexity invariant violated: w > 3"

**Cause:** Too many unresolved material variables.

**Solution:**
1. Resolve some variables before requesting permission
2. Decompose operation into smaller sub-operations
3. Review variable classification - are some incorrectly marked as material?
4. Apply override if justified (emergency situations only)

### Problem: ImmediateStopTriggered during execution

**Cause:** Continuous authorization confirmation lost.

**Solution:**
1. Ensure deadman switch / confirmation callback is functioning
2. Check network connectivity if confirmation is remote
3. Implement graceful shutdown on immediate stop
4. Do not retry automatically - immediate stop is final

---

## Next Steps

1. **Read SPECIFICATION.md** - Understand the complete framework specification
2. **Review AUTHORITY.md** - Set up production authority token infrastructure
3. **Review VARIABLES.md** - Master material variable classification
4. **Review ERROR_HANDLING.md** - Understand all exception types
5. **Study examples/** - See complete working examples

---

**End of Integration Guide**
