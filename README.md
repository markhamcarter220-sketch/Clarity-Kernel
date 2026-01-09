# Clarity Kernel

**Safety-Critical Reasoning Governance Framework with Bounded-Interface SAT Enforcement (w ≤ 3)**

Version 1.2.0

## Overview

The Clarity Kernel is a governance framework that enforces **when** reasoning, decisions, or actions are permitted to proceed. It does not generate answers—it determines **whether continuation is allowed**.

This is safety-critical code. All invariant violations raise exceptions. Stop means stop.

## Why This Exists

Most systems fail not because they lack capability, but because they lack
boundaries.

The Clarity Kernel exists to enforce hard limits on reasoning and execution in
systems where ambiguity, overreach, or implicit authority can cause harm. It is
designed to fail closed, stop on uncertainty, and preserve human authority at
all times.

This framework deliberately prioritizes:
- Determinism over convenience
- STOP over guessing
- Explicit authority over inferred intent
- Structural clarity over optimization

Clarity Kernel is not an agent, not a policy engine, and not a recommendation
system. It is a governance layer that decides whether an operation may proceed
at all.

## Core Principle

> If continuation can cause harm while **clarity**, **authority**, **attention**, or **constraint resolution** is insufficient, the system must not continue.

This overrides helpfulness, completeness, optimization, confidence, and fluency.

## Hard Invariants (Non-Negotiable)

1. **I-1: Clarity** — If definitions/thresholds/constraints are ambiguous → STOP
2. **I-2: Authority** — If authority is not explicit and verifiable → STOP
3. **I-3: Attention** — If harm possible without sustained attention → CONTINUOUS AUTH REQUIRED
4. **I-4: Truth** — Never indicate "allowed" while any invariant is unsatisfied
5. **I-5: Logging** — All violations logged immutably, nothing suppressed
6. **I-6: Silence** — Guessing is forbidden; silence is valid output
7. **I-7: Complexity** — If w > 3 → STOP or DECOMPOSE (never guess)

## Interface Width (w ≤ 3)

The kernel measures **w**: the number of unresolved material variables affecting the permission decision.

- **w ≤ 3**: Proceed
- **w > 3**: DECOMPOSE, ESCALATE, or STOP

No probabilistic collapse or guessing allowed to reduce w.

## Control Modes

### Momentary Authorization
Single authorization, permitted only if ALL true:
- Outcome is reversible
- Risk does not increase over time
- No new critical information can emerge
- w ≤ 3 at authorization
- Execution window is bounded

### Continuous Authorization
Ongoing confirmation required if ANY true:
- Outcome is irreversible
- Compliance/safety exposure exists
- Context may change during execution
- Ambiguity exists at initiation
- w may fluctuate during execution
- Execution window is extended

**Loss of confirmation → IMMEDIATE STOP** (no partial completion)

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
)

# Initialize kernel
kernel = ClarityKernel()

# Create permission request
request = PermissionRequest(
    operation_id="example_op",
    variables=[
        Variable("param1", resolved=True, material=True, value=42),
        Variable("param2", resolved=True, material=False, value="test"),
    ],
    required_definitions={"mode": "safe", "target": "production"},
    required_thresholds={"max_retries": 3, "timeout": 30},
    required_constraints=["all systems operational"],
    authority=AuthorityToken(
        source="operator_alice",
        verifiable=True,
        scope="execute_operation"
    ),
    required_scope="execute_operation",
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
    harm_scenario=""
)

# Request permission
response = kernel.request_permission(request)

if response.granted:
    print(f"Permission granted in {response.control_mode.value} mode")
    print(f"Measured width: w={response.measured_w}")
    print(f"Satisfied invariants: {response.satisfied_invariants}")
else:
    print(f"Permission denied: {response.denial_reason}")
```

## State Machine

### Normal Mode
```
IDLE → PRECONDITIONS_VALID → WIDTH_OK → AUTHORIZED → EXECUTING → COMPLETE
```

### Continuous Mode
```
IDLE → PRECONDITIONS_VALID → WIDTH_OK → CONTINUOUS_AUTH_REQUIRED →
EXECUTING (confirmation maintained) → IMMEDIATE_STOP (on loss)
```

### Abnormal/Override Mode (Break-Glass)
```
INVARIANT_UNSATISFIABLE → EXPLICIT_HUMAN_OVERRIDE → ABNORMAL_EXECUTION →
PERSISTENT_WARNING → RESOLUTION → RETURN_TO_SAFE_STATE
```

**No silent transitions permitted.**

## Break-Glass Override

Override is permitted only when:
- An invariant cannot be satisfied due to known limitation
- A human explicitly authorizes override (verifiable identity/role)
- Override state is persistently visible
- All override actions are logged immutably

**Override does not remove invariants**—it changes operating mode to ABNORMAL.

```python
kernel.apply_override(
    override_signature="admin_john_doe",
    unsatisfiable_invariants=["I-7"],
    justification="Emergency: width exceeded due to system integration requirements"
)
```

## Immediate Stop Semantics

When stop triggers:
- Execution halts immediately
- Reasoning halts immediately
- No automatic retry
- No partial completion
- No background continuation

**Stop means stop.**

## Testing

Run all tests:
```bash
pytest
```

Run specific test file:
```bash
pytest tests/test_invariants.py
pytest tests/test_control_modes.py
pytest tests/test_state_machine.py
pytest tests/test_override.py
```

Run with coverage:
```bash
pytest --cov=clarity_kernel --cov-report=html
```

## Architecture

```
clarity_kernel/
├── ssl.py              # Stable Structural Layer (main enforcement)
├── invariants.py       # Seven hard invariants + validators
├── state_machine.py    # State transitions (Normal/Continuous/Abnormal)
├── control_modes.py    # Momentary vs Continuous authorization
├── logging.py          # Immutable append-only audit log
└── ail.py              # Adaptive Interaction Layer (optional, non-normative)
```

## Implementer Rules (Mandatory)

- Do not optimize the kernel
- Do not soften invariants
- Do not infer intent or values to bypass gates
- Do not collapse ambiguity probabilistically

If uncertain:
- Pause
- Signal explicitly what is missing
- Escalate to HIL (Human-in-the-Loop)

**Silence is correct.**

## Anti-Patterns (Forbidden)

### ⚠ DO NOT Mark Safety-Critical Variables as Non-Material

```python
# ✗ WRONG: Gaming w≤3 by misclassifying material variables
variables = [
    Variable("dosage_mg", resolved=False, material=False, value=None),  # FRAUD
    Variable("patient_weight", resolved=False, material=False, value=None),  # FRAUD
]
# w=0 (falsely reported) - actual w=2
```

**Why this is forbidden:**
- Undermines the entire safety guarantee
- Violates I-7 (Complexity Invariant) through fraud
- See `docs/VARIABLES.md` for classification guide

**Correct:**
```python
# ✓ CORRECT: Honest classification
variables = [
    Variable("dosage_mg", resolved=False, material=True, value=None),
    Variable("patient_weight", resolved=False, material=True, value=None),
]
# w=2 (correctly reported) - requires human input for both
```

**Mechanical Detection:**
The kernel mechanically detects w-counting fraud:
```python
from clarity_kernel import detect_variable_bundling, detect_probabilistic_collapse, validate_material_classification

# Detects bundling ("_and_", "_config", "_options", generic names)
fraud = detect_variable_bundling(variables)

# Detects guessing (variables resolved without explicit input)
fraud = detect_probabilistic_collapse(variables_before, variables_after)

# Detects misclassification (safety-critical marked non-material)
validate_material_classification(variables, safety_critical_names={"dosage_mg", "patient_weight"})
```
See `examples/06_w_counting_fraud.py` for complete fraud detection demonstrations.

### ⚠ DO NOT Bundle Multiple Concerns into One Variable

```python
# ✗ WRONG: Variable bundling to game w≤3
variables = [
    Variable("patient_config_and_dosage", resolved=False, material=True, value=None),  # FRAUD
]
# Hides 4 material concerns (dosage, weight, drug, route) in one variable
# w=1 (fraudulent) - should be w=4
```

**Why this is forbidden:**
- Artificially reduces w by hiding multiple material concerns
- Violates I-7 enforcement through structural fraud
- Detected by: name patterns ("_and_", "_config"), dict bundling

**Correct:**
```python
# ✓ CORRECT: Separate variable for each material concern
variables = [
    Variable("dosage_mg", resolved=False, material=True, value=None),
    Variable("patient_weight_kg", resolved=False, material=True, value=None),
    Variable("drug_name", resolved=False, material=True, value=None),
    Variable("route", resolved=False, material=True, value=None),
]
# w=4 (honest) - triggers STOP or DECOMPOSE (as required)
```

### ⚠ DO NOT Guess Values to Reduce w (Probabilistic Collapse)

```python
# ✗ WRONG: Guessing values to artificially reduce w
# Before: w=3 (at limit)
variables_before = [
    Variable("dosage", resolved=False, material=True, value=None),
    Variable("route", resolved=False, material=True, value=None),
    Variable("frequency", resolved=False, material=True, value=None),
]

# After: Guess dosage and route to add 4th variable without exceeding w
variables_after = [
    Variable("dosage", resolved=True, material=True, value=50),  # GUESSED
    Variable("route", resolved=True, material=True, value="oral"),  # GUESSED
    Variable("frequency", resolved=False, material=True, value=None),
    Variable("drug_name", resolved=False, material=True, value=None),  # New
]
# w=2 (fraudulent) - guessed to avoid w=4
```

**Why this is forbidden:**
- Violates I-6 (Silence Invariant) - guessing is forbidden
- Introduces assumptions without authority
- May cause incorrect or unsafe behavior

**Correct:**
```python
# ✓ CORRECT: STOP or DECOMPOSE when w would exceed 3
if w_after_adding_variable > 3:
    # Option 1: Request explicit values
    raise ComplexityInvariantViolation("w=4 exceeds limit. Provide explicit values.")

    # Option 2: Decompose into smaller requests
    sub_request_1 = [Variable("dosage", ...)]  # w=1
    sub_request_2 = [Variable("route", ...), Variable("frequency", ...)]  # w=2

    # NEVER: Guess values to reduce w
```

### ⚠ DO NOT Use Placeholder Authority Tokens in Production

```python
# ✗ WRONG: Placeholder signatures in production
authority = AuthorityToken(
    source="admin",
    verifiable=True,
    scope="*",
    signature=b'\x00' * 64,  # Placeholder - NOT cryptographically signed
    timestamp=int(time.time()),
    nonce=os.urandom(32),
    issuer_pubkey=b'\x00' * 32  # Placeholder
)
```

**Why this is forbidden:**
- Violates I-2 (Authority Invariant) - not verifiable
- No cryptographic proof of authorization
- Anyone can forge tokens

**Correct:**
```python
# ✓ CORRECT: Real Ed25519 signature
# See docs/AUTHORITY.md and examples/02_authority_token.py
authority = issue_authority_token(
    source="admin_alice",
    scope="file.read",
    signing_key=load_private_key()  # Real Ed25519 key
)
```

### ⚠ DO NOT Guess or Infer Values to Bypass Invariants

```python
# ✗ WRONG: Inferring values to bypass I-6 (Silence)
if not file_path_provided:
    file_path = "/tmp/default.txt"  # Guessing
```

**Why this is forbidden:**
- Violates I-6 (Silence Invariant)
- Introduces assumptions user didn't make
- May cause incorrect or unsafe behavior

**Correct:**
```python
# ✓ CORRECT: Require explicit value or STOP
if not file_path_provided:
    raise ClarityInvariantViolation(
        "file_path is ambiguous - must be explicitly provided",
        ambiguous_elements=["file_path"]
    )
```

### ⚠ DO NOT Retry Automatically After ImmediateStopTriggered

```python
# ✗ WRONG: Automatic retry after stop
try:
    execute_operation()
except ImmediateStopTriggered:
    time.sleep(1)
    execute_operation()  # FORBIDDEN
```

**Why this is forbidden:**
- Violates immediate stop semantics
- Stop means stop (no retry, no partial completion)
- Requires explicit human re-authorization

**Correct:**
```python
# ✓ CORRECT: Log stop and escalate
try:
    execute_operation()
except ImmediateStopTriggered as e:
    logger.critical(f"STOP: {e.trigger}")
    preserve_state_for_review()
    notify_human_operator()
    # Do NOT retry
```

### ⚠ DO NOT Arbitrate Between Conflicting Valid Authorities

```python
# ✗ WRONG: Choosing between conflicting authorities
if authority_a.timestamp > authority_b.timestamp:
    chosen_authority = authority_a  # Authority laundering
```

**Why this is forbidden:**
- Violates SBAA (Split-Brain Authority Axiom)
- Kernel cannot choose between valid authorities
- Constitutes authority laundering

**Correct:**
```python
# ✓ CORRECT: Detect conflict and FREEZE
if detect_authority_conflict(authority_a, authority_b):
    transition_to_frozen()
    escalate_to_human_resolution()
    # Do NOT execute
```

### ⚠ DO NOT Suppress or Modify Log Entries

```python
# ✗ WRONG: Filtering or suppressing logs
def log_authorization(granted, authority_source, ...):
    if not granted:
        return  # Suppressing denial logs - FORBIDDEN
```

**Why this is forbidden:**
- Violates I-5 (Logging Invariant)
- All events must be logged immutably
- Nothing suppressed, nothing mutated

**Correct:**
```python
# ✓ CORRECT: Log everything, append-only
def log_authorization(granted, authority_source, ...):
    entry = create_log_entry(granted, authority_source, ...)
    append_to_immutable_log(entry)  # All events logged
```

### ⚠ DO NOT Claim ALLOWED While Invariants Are Unsatisfied

```python
# ✗ WRONG: Claiming success while invariants violated
response = PermissionResponse(
    granted=True,
    satisfied_invariants={"I-1", "I-2"},  # I-7 not satisfied
    # ...
)
```

**Why this is forbidden:**
- Violates I-4 (Truth Invariant)
- Misrepresents safety state
- May enable unsafe execution

**Correct:**
```python
# ✓ CORRECT: Deny if any invariant unsatisfied
all_invariants = {"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"}
if satisfied_invariants != all_invariants:
    raise TruthInvariantViolation(
        "Cannot claim ALLOWED with unsatisfied invariants",
        unsatisfied_invariants=list(all_invariants - satisfied_invariants)
    )
```

## Canonical Statement

> No clarity → no continuation
> No authority → no decision
> If w > 3 → decompose, escalate, or stop
> No attention → no execution

## AIL Wrapper (Optional, Non-Normative)

The Adaptive Interaction Layer (AIL) provides an optional wrapper for interactive clarification without modifying SSL behavior.

### Key Points

- **AIL is NOT part of the canonical SSL**
- SSL remains the authoritative decision layer
- AIL provides UX conveniences only
- All invariants and STOP semantics remain unchanged

### Usage

```python
from clarity_kernel import ClarityKernel, AILWrapper, AILSession, AILResponseType

# Create kernel and AIL wrapper
kernel = ClarityKernel()
session = AILSession(max_clarifications=2)
ail = AILWrapper(kernel, session)

# Process request through AIL
response = ail.step(request)

if response.response_type == AILResponseType.CLARIFY:
    print(response.message)  # "To proceed without assumptions, provide..."
elif response.response_type == AILResponseType.TAD:
    print(response.message)  # Terminal Ambiguity Declaration
elif response.response_type == AILResponseType.SILENCE:
    pass  # No output after TAD
elif response.response_type == AILResponseType.PASSTHROUGH:
    # SSL decision unchanged
    if response.ssl_response:
        print(f"Permission granted: {response.ssl_response.granted}")
```

### Behavior

When ambiguity is detected (I-1 violation):
1. First request: CLARIFY
2. Second request (same input): CLARIFY
3. Third request (same input): TAD (Terminal Ambiguity Declaration)
4. Fourth+ request (same input): SILENCE

New input or resolved ambiguity resets the session.

Non-ambiguity STOPs (I-2, I-3, etc.) pass through unchanged.

## Roadmap

Planned and potential future work:

- v1.2 — Reference AIL (Adaptive Interaction Layer) wrapper
- v1.3 — Pluggable invariant registry
- v1.4 — Configurable audit log backends
- v1.5 — Additional real-world examples (LLM tools, APIs, file systems)
- v2.0 — Language-agnostic specification

All roadmap items must preserve existing invariants and STOP semantics.

## License

MIT

## Documentation

See `SPECIFICATION.md` for the complete canonical specification (v1.2.0).

## Version

SSL Version: v1.2.0
Status: Canonical / Implementer-Facing
Scope: Abstract / AI-native
