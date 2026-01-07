# Clarity Kernel

**Safety-Critical Reasoning Governance Framework with Bounded-Interface SAT Enforcement (w ≤ 3)**

Version 1.1.0

## Overview

The Clarity Kernel is a governance framework that enforces **when** reasoning, decisions, or actions are permitted to proceed. It does not generate answers—it determines **whether continuation is allowed**.

This is safety-critical code. All invariant violations raise exceptions. Stop means stop.

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

## License

MIT

## Documentation

See `SPECIFICATION.md` for the complete canonical specification (v1.1.0).

## Version

SSL Version: v1.1.0
Status: Canonical / Implementer-Facing
Scope: Abstract / AI-native
