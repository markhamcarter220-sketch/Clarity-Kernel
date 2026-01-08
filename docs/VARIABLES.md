# Variable Classification Guide
## Material vs. Non-Material Variables

**Version:** 1.0
**Framework Version:** Clarity Kernel v1.2.0
**Status:** Normative Specification

---

## Purpose

This document specifies the **material variable classification** required by Invariant I-7 (Complexity).

The Clarity Kernel enforces that interface width `w ≤ 3`, where:
```
w := count(variables WHERE resolved=FALSE AND material=TRUE)
```

This classification determines which unresolved variables count toward the complexity limit.

---

## Core Principle

**Not all unknowns are equally critical.**

Some variables affect safety and correctness (material). Others are metadata, logging, or optimization hints (non-material).

Misclassifying variables to game the w≤3 constraint undermines the entire safety guarantee.

---

## Formal Definition

### Material Variable

A variable is **material** if ANY of the following are true:

1. **Safety-Affecting:**
   - Variable's value determines whether operation is safe to execute
   - Example: `structural_integrity` in freight loading scenario
   - Example: `dosage_amount` in medical device control

2. **Correctness-Affecting:**
   - Variable's value determines whether operation will produce correct result
   - Example: `file_path` in file read operation
   - Example: `account_id` in financial transaction

3. **Authorization-Affecting:**
   - Variable's value determines whether operation is authorized
   - Example: `user_role` in access control decision
   - Example: `required_clearance` in classified data access

4. **Branching-Critical:**
   - Variable's value determines which execution path is taken
   - Example: `operation_mode` that switches between read/write behavior
   - Example: `priority_level` that routes requests to different processors

5. **Undefined-Behavior:**
   - Variable's absence causes undefined or unpredictable behavior
   - Example: `buffer_size` where missing value causes memory errors
   - Example: `timeout_seconds` where missing value causes infinite wait

### Non-Material Variable

A variable is **non-material** if ALL of the following are true:

1. **Has Safe Default:**
   - Variable has a well-defined default that preserves correctness
   - Default does not reduce safety
   - Default does not change operation semantics
   - Example: `log_level="INFO"` (defaults to INFO)

2. **Metadata Only:**
   - Variable is used solely for logging, telemetry, debugging, or analytics
   - Variable does not affect execution flow
   - Variable could be omitted entirely without changing behavior
   - Example: `request_id` for tracing
   - Example: `user_agent` for analytics

3. **Optimization Hint:**
   - Variable provides performance hints but does not affect correctness
   - Operation succeeds identically with or without hint
   - Example: `cache_ttl` (caching is optimization, not requirement)
   - Example: `preferred_region` (routing hint, but any region works)

---

## Decision Tree

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

---

## Examples

### Material Variables

**Example 1: File Operations**
```python
Variable(name="file_path", resolved=True, material=True, value="/etc/config.yaml")
```
- **Justification:** Determines which file is accessed (correctness-affecting)
- **If unresolved:** Operation cannot proceed (undefined which file to read)

**Example 2: Medical Dosage**
```python
Variable(name="dosage_mg", resolved=False, material=True, value=None)
```
- **Justification:** Determines safety of administration (safety-affecting)
- **If unresolved:** Cannot safely administer (w += 1)

**Example 3: Access Control**
```python
Variable(name="required_role", resolved=True, material=True, value="admin")
```
- **Justification:** Determines authorization (authorization-affecting)
- **If unresolved:** Cannot verify access rights

**Example 4: Execution Mode**
```python
Variable(name="mode", resolved=False, material=True, value=None)
```
- **Justification:** Determines execution path (branching-critical)
- **If unresolved:** Ambiguous which code path to execute

**Example 5: Network Timeout**
```python
Variable(name="timeout_seconds", resolved=True, material=True, value=30)
```
- **Justification:** Determines behavior (undefined-behavior if missing)
- **If unresolved:** Might hang indefinitely or use unsafe default

### Non-Material Variables

**Example 1: Request Tracing**
```python
Variable(name="request_id", resolved=True, material=False, value="req_12345")
```
- **Justification:** Used only for logging (metadata-only)
- **Has safe default:** Empty string or generated UUID
- **Does not affect:** Safety, correctness, authorization

**Example 2: User Agent**
```python
Variable(name="user_agent", resolved=True, material=False, value="curl/7.68.0")
```
- **Justification:** Used only for telemetry (metadata-only)
- **Has safe default:** "unknown"
- **Does not affect:** Operation behavior

**Example 3: Cache TTL**
```python
Variable(name="cache_ttl", resolved=False, material=False, value=None)
```
- **Justification:** Performance hint (optimization-hint)
- **Has safe default:** No caching (always fetch fresh)
- **Does not affect:** Correctness (just slower without cache)

**Example 4: Log Level**
```python
Variable(name="log_level", resolved=True, material=False, value="DEBUG")
```
- **Justification:** Controls verbosity (metadata-only)
- **Has safe default:** "INFO"
- **Does not affect:** Operation outcome

**Example 5: Preferred Region**
```python
Variable(name="preferred_region", resolved=False, material=False, value=None)
```
- **Justification:** Routing hint (optimization-hint)
- **Has safe default:** Any available region
- **Does not affect:** Correctness (all regions equivalent)

---

## Common Pitfalls

### Pitfall #1: Gaming w≤3 by Marking Everything Non-Material

**Incorrect:**
```python
# 10 unresolved variables, but only 2 marked material → w=2 ✓ (passes)
variables = [
    Variable("dosage", resolved=False, material=True, value=None),
    Variable("patient_weight", resolved=False, material=True, value=None),
    Variable("drug_name", resolved=False, material=False, value=None),  # WRONG
    Variable("administration_route", resolved=False, material=False, value=None),  # WRONG
    # ... 6 more incorrectly marked as non-material
]
```

**Problem:** `drug_name` and `administration_route` are safety-critical. Marking them non-material to pass w≤3 is fraud.

**Correct:**
```python
# All safety-critical variables marked material → w=4 (fails, must decompose)
variables = [
    Variable("dosage", resolved=False, material=True, value=None),
    Variable("patient_weight", resolved=False, material=True, value=None),
    Variable("drug_name", resolved=False, material=True, value=None),
    Variable("administration_route", resolved=False, material=True, value=None),
]
# Kernel returns STOP (w=4 > 3) → Forces decomposition or explicit values
```

### Pitfall #2: Assuming "Optional" Means "Non-Material"

**Incorrect reasoning:**
- "This parameter is optional in the API, so it's non-material"

**Reality:**
- Optional ≠ non-material
- Optional parameters often have defaults, but defaults may not be safe for all contexts

**Example:**
```python
# API signature: delete_file(path, confirm=False)
# "confirm" is optional, but is it non-material?

Variable("confirm", resolved=False, material=???, value=None)
```

**Analysis:**
- If `confirm=False` allows deletion without confirmation → **MATERIAL** (safety-affecting)
- If `confirm` only affects logging verbosity → **NON-MATERIAL**

**Decision:** **MATERIAL** - Determines whether safety check is performed

### Pitfall #3: Optimization Hints That Affect Correctness

**Ambiguous case:**
```python
Variable("use_cache", resolved=False, material=???, value=None)
```

**Analysis:**
- If cache is pure optimization (fetch from cache vs. fetch fresh, result identical) → **NON-MATERIAL**
- If cache might be stale and staleness affects correctness → **MATERIAL**

**Decision depends on context:**
- **Financial system:** Stale cache could show wrong balance → **MATERIAL**
- **CDN asset delivery:** Stale cache acceptable → **NON-MATERIAL**

**Rule:** If cache staleness affects correctness → **MATERIAL**

### Pitfall #4: Logging Variables That Affect Execution

**Incorrect:**
```python
Variable("debug_mode", resolved=False, material=False, value=None)  # WRONG
```

**Problem:** If `debug_mode=True` changes execution (e.g., disables security checks for debugging) → **MATERIAL**

**Correct:**
```python
Variable("debug_mode", resolved=False, material=True, value=None)
```

**Rule:** If variable changes execution behavior (even "just for debugging") → **MATERIAL**

---

## Enforcement

### Self-Check Questions

Before classifying a variable as **non-material**, answer:

1. ☐ Does the variable have a safe default?
2. ☐ Is the default correct for ALL possible contexts?
3. ☐ Does omitting the variable preserve safety?
4. ☐ Does omitting the variable preserve correctness?
5. ☐ Is the variable used ONLY for logging/telemetry?
6. ☐ Would a safety auditor accept this classification?

If ANY answer is NO → Variable is **MATERIAL**

### Code Review Checklist

When reviewing PermissionRequest construction:

- [ ] All safety-affecting variables marked material
- [ ] All correctness-affecting variables marked material
- [ ] All authorization-affecting variables marked material
- [ ] No gaming of w≤3 by misclassification
- [ ] Each non-material classification has written justification
- [ ] Variables with defaults: is default safe for ALL contexts?

---

## Testing Guide

### Test: Material Classification

```python
def test_material_classification():
    """Verify all safety-critical variables are marked material."""

    request = PermissionRequest(...)

    # Extract all unresolved material variables
    unresolved_material = [
        v for v in request.variables
        if not v.resolved and v.material
    ]

    # For safety-critical operations, verify critical variables are included
    if request.operation_id.startswith("medical_"):
        assert any(v.name == "dosage" for v in unresolved_material)
        assert any(v.name == "patient_id" for v in unresolved_material)

    # Verify w is measured correctly
    measured_w = len(unresolved_material)
    assert measured_w <= 3, f"Interface width {measured_w} exceeds limit"
```

### Test: Non-Material Classification

```python
def test_nonmaterial_has_safe_default():
    """Verify non-material variables have safe defaults."""

    request = PermissionRequest(...)

    for v in request.variables:
        if not v.material:
            # Non-material variable must have safe default
            assert v.name in KNOWN_SAFE_DEFAULTS, \
                f"{v.name} marked non-material but has no safe default"

            # Verify operation succeeds with default
            result = execute_with_default(request, v.name)
            assert result.safe and result.correct
```

---

## Specification Update

This guide formalizes Section 5.7 (I-7: Complexity Invariant) of SPECIFICATION.md.

### I-7 Formal Definition

```
I-7 (Complexity Invariant):

Let w := count(v ∈ variables WHERE v.resolved = FALSE ∧ v.material = TRUE)

If w > 3, then I-7 := FALSE

A variable v is "material" if and only if:
  v affects safety
  ∨ v affects correctness
  ∨ v affects authorization
  ∨ v determines execution path
  ∨ v's absence causes undefined behavior

A variable v is "non-material" if and only if:
  v has safe default that preserves correctness
  ∧ v is used only for metadata (logging, telemetry)
  ∧ v does not affect execution flow

When in doubt, classify as material.
Prefer STOP over risk.
```

---

## Compliance Requirement

**Before deploying Clarity Kernel in production:**

Every PermissionRequest constructor call MUST:
1. Document material classification decision for each variable
2. Justify why non-material variables are safe to leave unresolved
3. Pass code review specifically checking for w≤3 gaming

**Example documentation:**
```python
request = PermissionRequest(
    variables=[
        # MATERIAL: Determines which file to access (correctness-critical)
        Variable("file_path", resolved=True, material=True, value="/etc/config.yaml"),

        # NON-MATERIAL: Logging only, has safe default (empty string)
        Variable("request_id", resolved=True, material=False, value="req_123"),
    ],
    ...
)
```

---

**End of Variable Classification Guide**
