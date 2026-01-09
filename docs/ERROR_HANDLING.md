# Error Handling Guide
## Exception Reference and Handling Patterns

**Version:** 1.0
**Framework Version:** Clarity Kernel v1.2.0
**Status:** Normative Reference

---

## Table of Contents

1. [Exception Philosophy](#exception-philosophy)
2. [Exception Hierarchy](#exception-hierarchy)
3. [SSL Exceptions](#ssl-exceptions)
4. [Invariant Violations](#invariant-violations)
5. [State Machine Exceptions](#state-machine-exceptions)
6. [Control Mode Exceptions](#control-mode-exceptions)
7. [LTC Exceptions](#ltc-exceptions)
8. [Logging Exceptions](#logging-exceptions)
9. [Handling Patterns](#handling-patterns)
10. [Production Best Practices](#production-best-practices)

---

## Exception Philosophy

### Hard Failures, No Warnings

The Clarity Kernel enforces **hard invariants**. When an invariant is violated:
- An exception is **always** raised
- **No** warnings or soft failures
- **No** automatic recovery or retry
- **No** silent degradation

### Exception as Verdict

Exceptions are not errors - they are **verdicts**:
- **PermissionDenied:** The operation may not proceed
- **ImmediateStopTriggered:** Execution must halt now
- **InvariantViolation:** A safety constraint is unsatisfied

These are correct outputs, not bugs to fix.

### Three Response Categories

1. **Resolve and Retry:** Fix the issue (e.g., obtain authority, resolve variable)
2. **Decompose:** Break operation into smaller pieces
3. **Escalate:** Request human intervention or apply override

---

## Exception Hierarchy

```
Exception (Python base)
│
├─ PermissionDenied (SSL)
│   └─ reason: str
│   └─ kernel_state: str
│
├─ ImmediateStopTriggered (SSL)
│   └─ trigger: str
│
├─ InvariantViolation (Base for all invariants)
│   ├─ invariant_id: str
│   ├─ context: dict[str, Any]
│   │
│   ├─ ClarityInvariantViolation (I-1)
│   │   └─ ambiguous_elements: list[str]
│   │
│   ├─ AuthorityInvariantViolation (I-2)
│   │   └─ required_authority: str
│   │
│   ├─ AttentionInvariantViolation (I-3)
│   │   └─ harm_scenario: str
│   │
│   ├─ TruthInvariantViolation (I-4)
│   │   └─ unsatisfied_invariants: list[str]
│   │
│   ├─ LoggingInvariantViolation (I-5)
│   │   └─ suppression_attempt: str
│   │
│   ├─ SilenceInvariantViolation (I-6)
│   │   └─ guessed_value: Any
│   │   └─ variable_name: str
│   │
│   └─ ComplexityInvariantViolation (I-7)
│       └─ measured_w: int
│       └─ unresolved_variables: list[str]
│
├─ InvalidStateTransition (State Machine)
│   └─ from_state: KernelState
│   └─ to_state: KernelState
│   └─ reason: str
│
├─ SilentTransitionAttempt (State Machine)
│   └─ from_state: KernelState
│   └─ to_state: KernelState
│
├─ ControlModeViolation (Base for control modes)
│   │
│   ├─ MomentaryAuthorizationForbidden
│   │   └─ failed_conditions: list[str]
│   │
│   ├─ ContinuousAuthorizationLost
│   │   └─ lost_at: datetime
│   │
│   └─ ContinuousAuthorizationRequired
│       └─ triggering_conditions: list[str]
│
├─ LTCViolation (LTC)
│   └─ reason: str
│   └─ context: dict[str, Any]
│
└─ LogSuppressionAttempt (Logging)
    └─ event_type: str
```

---

## SSL Exceptions

### PermissionDenied

**Raised when:** Permission to proceed is denied due to invariant violation.

**Attributes:**
- `reason` (str): Human-readable denial reason
- `kernel_state` (str): Kernel state at time of denial

**Common Causes:**
- One or more invariants violated
- Authority token missing or invalid
- Interface width w > 3
- Ambiguous definitions/thresholds

**Handling Pattern:**

```python
from clarity_kernel import PermissionDenied

try:
    response = kernel.request_permission(request)
except PermissionDenied as e:
    # Log denial
    logger.error(
        "permission_denied",
        reason=e.reason,
        kernel_state=e.kernel_state,
        operation_id=request.operation_id
    )

    # Option 1: Notify user
    notify_user(f"Operation denied: {e.reason}")

    # Option 2: Escalate to human reviewer
    escalate_to_human(request, denial_reason=e.reason)

    # Option 3: Apply override (if justified and authorized)
    if is_emergency() and has_override_authority():
        kernel.apply_override(
            override_signature=get_override_signature(),
            unsatisfiable_invariants=["I-1"],  # Example
            justification=f"Emergency override: {e.reason}"
        )
        response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. Identify which invariant violated (check specific InvariantViolation types)
2. Fix the issue (obtain authority, resolve variables, clarify definitions)
3. Retry with corrected request
4. If cannot fix: escalate or apply override

---

### ImmediateStopTriggered

**Raised when:** Immediate stop condition is met (always fatal).

**Attributes:**
- `trigger` (str): What triggered the stop

**Common Causes:**
- Continuous authorization lost (deadman switch)
- Manual stop trigger
- Critical safety condition detected

**Handling Pattern:**

```python
from clarity_kernel import ImmediateStopTriggered

try:
    # Long-running operation with continuous auth
    for step in operation_steps:
        execute_step(step)
        guard.confirm()  # May trigger stop if confirmation lost

except ImmediateStopTriggered as e:
    # STOP is final - no retry
    logger.critical(
        "immediate_stop",
        trigger=e.trigger,
        message=str(e)
    )

    # Graceful shutdown
    cleanup_resources()
    notify_user(f"Operation stopped: {e.trigger}")

    # Do NOT retry automatically
    # Do NOT complete partial work
    # Do NOT continue in background
```

**Resolution Strategies:**
1. **Never** retry automatically
2. Perform graceful shutdown
3. Preserve state for manual review
4. Require explicit human re-authorization before retry

---

## Invariant Violations

### ClarityInvariantViolation (I-1)

**Raised when:** Required definitions, thresholds, or constraints are ambiguous or undefined.

**Attributes:**
- `ambiguous_elements` (list[str]): Which elements are ambiguous

**Example:**

```python
from clarity_kernel import ClarityInvariantViolation

try:
    response = kernel.request_permission(request)
except ClarityInvariantViolation as e:
    print(f"Ambiguous elements: {e.ambiguous_elements}")
    # Example: ["threshold_temperature", "constraint_pressure_range"]

    # Resolution: Clarify ambiguous elements
    for element in e.ambiguous_elements:
        if element.startswith("threshold_"):
            # Provide explicit threshold
            request.required_thresholds[element] = get_explicit_threshold(element)
        elif element.startswith("constraint_"):
            # Provide explicit constraint
            request.required_constraints.append(get_explicit_constraint(element))

    # Retry with clarified request
    response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. **Identify ambiguity:** Check `ambiguous_elements` list
2. **Resolve definitions:** Provide concrete, non-ambiguous values
3. **Resolve thresholds:** Provide explicit numeric thresholds
4. **Resolve constraints:** State constraints explicitly
5. **Decompose:** Break operation into smaller, clearer sub-operations

---

### AuthorityInvariantViolation (I-2)

**Raised when:** Authority to proceed is not explicit and verifiable.

**Attributes:**
- `required_authority` (str): The scope of authority required

**Example:**

```python
from clarity_kernel import AuthorityInvariantViolation

try:
    response = kernel.request_permission(request)
except AuthorityInvariantViolation as e:
    print(f"Required authority: {e.required_authority}")
    # Example: "file.write"

    # Resolution: Obtain authority token
    authority_token = obtain_authority_token(
        source=current_user,
        scope=e.required_authority
    )

    # Update request with authority
    request.authority = authority_token

    # Retry
    response = kernel.request_permission(request)
```

**Common Failure Reasons:**
- `authority` is None
- Signature verification failed
- Scope insufficient (e.g., granted "file.read" but required "file.write")
- Token expired (timestamp > MAX_TOKEN_AGE)
- Issuer not in trusted registry

**Resolution Strategies:**
1. **Obtain token:** Request token from authority server
2. **Verify signature:** Ensure Ed25519 signature is valid
3. **Check scope:** Ensure granted scope ⊇ required scope
4. **Check expiry:** Ensure timestamp within acceptable range
5. **Check issuer:** Ensure public key in TRUSTED_ISSUER_REGISTRY

---

### AttentionInvariantViolation (I-3)

**Raised when:** Continuous human attention required but not provided.

**Attributes:**
- `harm_scenario` (str): Description of potential harm without attention

**Example:**

```python
from clarity_kernel import AttentionInvariantViolation

try:
    response = kernel.request_permission(request)
except AttentionInvariantViolation as e:
    print(f"Harm scenario: {e.harm_scenario}")
    # Example: "Financial transfer may be fraudulent if context changes"

    # Resolution: Enable continuous mode
    request.triggers = ContinuousTriggers(
        outcome_irreversible=True,
        compliance_safety_exposure=True,
        context_may_change=True,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=True
    )

    # Provide confirmation mechanism
    def confirm_callback():
        return user_confirms_still_authorized()

    # Retry with continuous mode
    response = kernel.request_permission(request)
    if response.control_mode == ControlMode.CONTINUOUS:
        execute_with_continuous_auth(response.execution_guard, confirm_callback)
```

**Resolution Strategies:**
1. **Enable continuous mode:** Set appropriate triggers
2. **Implement confirmation:** Provide deadman switch mechanism
3. **Reduce harm:** Make operation reversible if possible
4. **Decompose:** Break into smaller operations with bounded harm

---

### TruthInvariantViolation (I-4)

**Raised when:** System claims ALLOWED while invariants are unsatisfied.

**Attributes:**
- `unsatisfied_invariants` (list[str]): Which invariants are unsatisfied

**Example:**

```python
from clarity_kernel import TruthInvariantViolation

try:
    response = kernel.request_permission(request)
except TruthInvariantViolation as e:
    print(f"Unsatisfied invariants: {e.unsatisfied_invariants}")
    # Example: ["I-1", "I-7"]

    # This should NOT happen in normal operation
    # Indicates kernel bug or corruption

    # Log critical error
    logger.critical(
        "truth_invariant_violated",
        unsatisfied=e.unsatisfied_invariants,
        message="Kernel attempted to claim ALLOWED with unsatisfied invariants"
    )

    # DO NOT PROCEED
    # Escalate to kernel maintainers
```

**Resolution Strategies:**
1. **Never** attempt to bypass
2. Log critical error
3. Escalate to kernel maintainers (potential bug)
4. Do not execute operation

---

### LoggingInvariantViolation (I-5)

**Raised when:** Event logging suppressed or mutated.

**Attributes:**
- `suppression_attempt` (str): What was attempted to suppress

**Example:**

```python
from clarity_kernel import LoggingInvariantViolation

try:
    response = kernel.request_permission(request)
except LoggingInvariantViolation as e:
    print(f"Suppression attempt: {e.suppression_attempt}")

    # This indicates logging infrastructure failure
    # or malicious suppression attempt

    logger.critical(
        "logging_invariant_violated",
        suppression_attempt=e.suppression_attempt
    )

    # DO NOT PROCEED - logging is mandatory
```

**Resolution Strategies:**
1. Verify logging infrastructure is functional
2. Check disk space / log storage
3. Check logger permissions
4. Do not proceed without functioning logs

---

### SilenceInvariantViolation (I-6)

**Raised when:** Attempting to guess unresolved variable value.

**Attributes:**
- `guessed_value` (Any): The value that was guessed
- `variable_name` (str): Which variable was guessed

**Example:**

```python
from clarity_kernel import SilenceInvariantViolation

try:
    response = kernel.request_permission(request)
except SilenceInvariantViolation as e:
    print(f"Guessed variable: {e.variable_name} = {e.guessed_value}")
    # Example: "dosage_mg = 50" (guessed from average)

    # Resolution: Obtain explicit value
    explicit_value = request_human_input(e.variable_name)

    # Update variable to resolved
    for var in request.variables:
        if var.name == e.variable_name:
            var = Variable(
                name=var.name,
                resolved=True,
                material=var.material,
                value=explicit_value
            )

    # Retry with explicit value
    response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. **Never** guess or infer values
2. Request explicit human input
3. Use sensor data if available
4. Decompose operation to avoid need for value

---

### ComplexityInvariantViolation (I-7)

**Raised when:** Interface width w > max_width (default 3).

**Attributes:**
- `measured_w` (int): The measured interface width
- `unresolved_variables` (list[str]): Names of unresolved material variables

**Example:**

```python
from clarity_kernel import ComplexityInvariantViolation

try:
    response = kernel.request_permission(request)
except ComplexityInvariantViolation as e:
    print(f"Interface width w={e.measured_w} > 3")
    print(f"Unresolved variables: {e.unresolved_variables}")
    # Example: ["dosage_mg", "patient_weight", "drug_name", "route"]

    # Strategy 1: Resolve some variables
    for var_name in e.unresolved_variables[:2]:  # Resolve first 2
        value = request_human_input(var_name)
        for var in request.variables:
            if var.name == var_name:
                var = Variable(var.name, True, var.material, value)

    # Strategy 2: Decompose operation
    sub_operations = decompose_into_smaller_ops(request)
    for sub_op in sub_operations:
        response = kernel.request_permission(sub_op)
        execute(sub_op)

    # Strategy 3: Apply override (emergency only)
    if is_emergency():
        kernel.apply_override(
            override_signature=get_override_signature(),
            unsatisfiable_invariants=["I-7"],
            justification=f"Emergency: w={e.measured_w} unavoidable"
        )
        response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. **Resolve variables:** Obtain values to reduce w
2. **Decompose:** Break into sub-operations with w ≤ 3 each
3. **Re-classify:** Review if some variables incorrectly marked material
4. **Override:** Apply break-glass override (emergency only)

---

## State Machine Exceptions

### InvalidStateTransition

**Raised when:** Invalid state transition attempted.

**Attributes:**
- `from_state` (KernelState): Current state
- `to_state` (KernelState): Attempted target state
- `reason` (str): Why transition is invalid

**Example:**

```python
from clarity_kernel import InvalidStateTransition

try:
    # Attempt to reset from invalid state
    kernel.reset()
except InvalidStateTransition as e:
    print(f"Invalid transition: {e.from_state} → {e.to_state}")
    print(f"Reason: {e.reason}")

    # Resolution: Follow valid state transition path
    if e.from_state == KernelState.EXECUTING:
        # Must complete execution first
        complete_execution()
        kernel.reset()
```

**Resolution Strategies:**
1. Follow valid state transition paths (see SPECIFICATION.md Section 7)
2. Complete current operation before transitioning
3. Check kernel state before operations

---

### SilentTransitionAttempt

**Raised when:** State transition attempted without logging.

**Attributes:**
- `from_state` (KernelState): Current state
- `to_state` (KernelState): Target state

**Example:**

```python
from clarity_kernel import SilentTransitionAttempt

# This should NOT happen - indicates kernel bug
try:
    response = kernel.request_permission(request)
except SilentTransitionAttempt as e:
    logger.critical(
        "silent_transition_attempt",
        from_state=e.from_state.value,
        to_state=e.to_state.value
    )

    # Escalate to kernel maintainers
```

**Resolution Strategies:**
1. Log critical error
2. Escalate to kernel maintainers (kernel bug)

---

## Control Mode Exceptions

### MomentaryAuthorizationForbidden

**Raised when:** Momentary authorization attempted but preconditions not met.

**Attributes:**
- `failed_conditions` (list[str]): Which preconditions failed

**Example:**

```python
from clarity_kernel import MomentaryAuthorizationForbidden

try:
    response = kernel.request_permission(request)
except MomentaryAuthorizationForbidden as e:
    print(f"Failed preconditions: {e.failed_conditions}")
    # Example: ["outcome_reversible", "execution_window_bounded"]

    # Resolution: Switch to continuous mode
    request.triggers = ContinuousTriggers(
        outcome_irreversible=True,
        compliance_safety_exposure=False,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=True
    )

    response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. Switch to continuous authorization mode
2. Modify operation to satisfy preconditions
3. Decompose into smaller momentary operations

---

### ContinuousAuthorizationLost

**Raised when:** Continuous authorization confirmation lost during execution.

**Attributes:**
- `lost_at` (datetime): When authorization was lost

**Example:**

```python
from clarity_kernel import ContinuousAuthorizationLost

try:
    for step in operation_steps:
        execute_step(step)
        guard.confirm()  # May raise if confirmation lost

except ContinuousAuthorizationLost as e:
    print(f"Authorization lost at: {e.lost_at}")

    # STOP execution immediately
    rollback_partial_work()
    notify_user("Operation stopped: authorization lost")

    # Do NOT continue or retry automatically
```

**Resolution Strategies:**
1. Stop execution immediately
2. Rollback partial work if possible
3. Preserve state for manual review
4. Require explicit re-authorization before retry

---

### ContinuousAuthorizationRequired

**Raised when:** Continuous mode required but momentary attempted.

**Attributes:**
- `triggering_conditions` (list[str]): Which triggers require continuous mode

**Example:**

```python
from clarity_kernel import ContinuousAuthorizationRequired

try:
    response = kernel.request_permission(request)
except ContinuousAuthorizationRequired as e:
    print(f"Continuous mode required due to: {e.triggering_conditions}")
    # Example: ["outcome_irreversible", "compliance_safety_exposure"]

    # Resolution: Provide continuous mode setup
    request.triggers = ContinuousTriggers(
        outcome_irreversible=True,
        compliance_safety_exposure=True,
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )

    response = kernel.request_permission(request)
```

**Resolution Strategies:**
1. Enable continuous authorization
2. Implement confirmation mechanism
3. Modify operation to eliminate triggers

---

## LTC Exceptions

### LTCViolation

**Raised when:** Illegitimate domain transfer attempted.

**Attributes:**
- `reason` (str): Why transfer is illegitimate
- `context` (dict[str, Any]): Additional context

**Example:**

```python
from clarity_kernel import LTCViolation

try:
    evaluation = ltc_enforcer.evaluate(transfer_request)
    if evaluation.verdict == LTCVerdict.DENY:
        raise LTCViolation(
            "Illegitimate transfer",
            reason=evaluation.reason_codes[0],
            context={"failed_invariants": evaluation.failed_invariants}
        )
except LTCViolation as e:
    print(f"Transfer denied: {e.reason}")
    print(f"Failed invariants: {e.context['failed_invariants']}")

    # Resolution: Provide explicit invariant-preserving mapping
    transfer_request.proposed_mapping = {
        "source_inv_1": "target_inv_1",
        "source_inv_2": "target_inv_2"
    }

    # Retry with explicit mapping
    evaluation = ltc_enforcer.evaluate(transfer_request)
```

**Resolution Strategies:**
1. Provide explicit invariant-preserving mapping
2. Prove invariant preservation
3. Do not attempt transfer by analogy or pattern matching

---

## Logging Exceptions

### LogSuppressionAttempt / LogMutationAttempt

**Raised when:** Attempt to suppress or mutate logs.

**Example:**

```python
# This should NOT happen - indicates malicious behavior or bug

try:
    # ... operations ...
except LogSuppressionAttempt as e:
    # Log critical security event
    security_logger.critical(
        "log_suppression_attempt",
        event_type=e.event_type,
        timestamp=datetime.utcnow()
    )

    # Escalate to security team
    escalate_to_security("Log suppression attempt detected")

    # DO NOT PROCEED
```

**Resolution Strategies:**
1. Escalate to security team
2. Audit recent operations
3. Do not proceed with operation

---

## Handling Patterns

### Pattern 1: Catch-Resolve-Retry

```python
def execute_with_retry(request: PermissionRequest, max_attempts: int = 3):
    """Attempt to resolve issues and retry."""
    for attempt in range(max_attempts):
        try:
            response = kernel.request_permission(request)
            return execute_operation(response)

        except ClarityInvariantViolation as e:
            # Resolve ambiguity
            resolve_ambiguous_elements(request, e.ambiguous_elements)

        except AuthorityInvariantViolation as e:
            # Obtain authority
            request.authority = obtain_authority_token(e.required_authority)

        except ComplexityInvariantViolation as e:
            # Resolve variables
            resolve_variables(request, e.unresolved_variables[:2])

    raise RuntimeError(f"Failed after {max_attempts} attempts")
```

### Pattern 2: Graceful Degradation

```python
def execute_with_degradation(request: PermissionRequest):
    """Try full operation, fall back to limited version."""
    try:
        response = kernel.request_permission(request)
        return execute_full_operation(response)

    except PermissionDenied as e:
        logger.warning(f"Full operation denied: {e.reason}")

        # Try limited/read-only version
        limited_request = create_limited_request(request)
        response = kernel.request_permission(limited_request)
        return execute_limited_operation(response)
```

### Pattern 3: Decompose on Complexity

```python
def execute_with_decomposition(request: PermissionRequest):
    """Decompose if w > 3."""
    try:
        response = kernel.request_permission(request)
        return execute_operation(response)

    except ComplexityInvariantViolation as e:
        logger.info(f"Decomposing: w={e.measured_w}")

        # Decompose into sub-operations
        sub_operations = decompose_operation(request)

        results = []
        for sub_op in sub_operations:
            response = kernel.request_permission(sub_op)
            results.append(execute_operation(response))

        return combine_results(results)
```

---

## Production Best Practices

### 1. Log All Exceptions

```python
try:
    response = kernel.request_permission(request)
except Exception as e:
    logger.error(
        "kernel_exception",
        exception_type=type(e).__name__,
        exception_message=str(e),
        operation_id=request.operation_id,
        traceback=traceback.format_exc()
    )
    raise
```

### 2. Never Suppress Exceptions

```python
# BAD: Silent suppression
try:
    response = kernel.request_permission(request)
except PermissionDenied:
    pass  # NEVER DO THIS

# GOOD: Explicit handling
try:
    response = kernel.request_permission(request)
except PermissionDenied as e:
    logger.error("permission_denied", reason=e.reason)
    notify_user(f"Operation denied: {e.reason}")
    raise  # Re-raise after logging
```

### 3. Distinguish Retryable vs Non-Retryable

```python
# Retryable: Can fix by obtaining authority, resolving variables
RETRYABLE_EXCEPTIONS = (
    ClarityInvariantViolation,
    AuthorityInvariantViolation,
    ComplexityInvariantViolation,
)

# Non-retryable: Fatal, requires human intervention
NON_RETRYABLE_EXCEPTIONS = (
    ImmediateStopTriggered,
    TruthInvariantViolation,
    LoggingInvariantViolation,
)

try:
    response = kernel.request_permission(request)
except RETRYABLE_EXCEPTIONS as e:
    handle_and_retry(e)
except NON_RETRYABLE_EXCEPTIONS as e:
    escalate_to_human(e)
```

### 4. Set Maximum Retry Attempts

```python
MAX_RETRY_ATTEMPTS = 3

for attempt in range(MAX_RETRY_ATTEMPTS):
    try:
        response = kernel.request_permission(request)
        break
    except ClarityInvariantViolation as e:
        if attempt == MAX_RETRY_ATTEMPTS - 1:
            raise  # Final attempt failed
        resolve_ambiguity(e)
```

### 5. Monitor Exception Rates

```python
# Track exception frequency
exception_counter = Counter()

try:
    response = kernel.request_permission(request)
except Exception as e:
    exception_counter[type(e).__name__] += 1

    # Alert if high rate
    if exception_counter[type(e).__name__] > 100:
        alert_ops_team(f"High rate of {type(e).__name__}")
```

---

**End of Error Handling Guide**
