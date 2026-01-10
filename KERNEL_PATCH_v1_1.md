# KERNEL PATCH v1.1 — Temporal Coherence, ASK Resolution, and Rollback Hardening

**Status:** ✅ Implemented
**Effective Date:** 2026-01-10
**Applies To:** Clarity Kernel v1.2.0

## Executive Summary

This patch introduces **bounded coherence tracking**, **monotonic ASK resolution**, **deeper rollback safety**, and **loop termination guarantees** to prevent unbounded drift, indefinite suspension, and adversarial ambiguity exploitation.

### Core Guarantees

1. **Temporal coherence remains O(1) bounded** over unbounded execution horizons
2. **ASK loops self-terminate** before silence (max 3 unresolved C-1)
3. **Progress is monotonic** (no infinite suspension from unresolved ambiguity)
4. **All cannon fires are logged** (complete audit trail)
5. **Rollbacks preserve valid history** (k* - 2 safety margin)

---

## 1. Temporal Coherence Layer (unAI OS)

### Problem

Without bounded tracking, temporal coherence slack `Coh_t` can snowball over long execution horizons, leading to semantic drift that compounds indefinitely.

### Solution

Implemented **TemporalCoherenceTracker** that enforces O(1) bounded coherence through:

**Update Rule:**
```
Coh_{t+1} = clip[0, Coh_max](Coh_t + Δ_drift(t) - δ_decay(λ, state))
```

Where:
- `Coh_t ≥ 0`: Current temporal coherence slack
- `δ_decay ∈ [0.02, 0.05]`: Per-step coherence decay
- `Coh_soft`: Soft coherence threshold (default: 0.5)
- `Coh_max`: Hard coherence ceiling (default: 1.0)

### Enforcement Mechanisms

**Soft-cap repair** (Coh > Coh_soft):
- Trigger minor projection Π_t
- Tighten meaning (drop lowest-confidence interpretations)
- Reduce slack assumptions
- Optionally reduce Coh by small constant (0.05)

**Hard-cap escalation** (Coh ≥ Coh_max):
- Escalate to governance
- Freeze optimization
- Require human or higher-order authority
- Raises `CoherenceViolation` exception

### Implementation

**Module:** `src/clarity_kernel/temporal_coherence.py`

**Key Classes:**
- `TemporalCoherenceTracker`: Main coherence tracker
- `CoherenceState`: State container with thresholds
- `ProjectionResult`: Structured projection audit record
- `CoherenceViolation`: Exception for hard cap violation

**Usage:**
```python
from clarity_kernel import TemporalCoherenceTracker

tracker = TemporalCoherenceTracker(
    coh_soft=0.5,
    coh_max=1.0
)

# Each reasoning step
tracker.step(
    drift_delta=0.1,  # Change in coherence
    lambda_param=1.0,
    state_complexity=2.0
)

# Check status
status = tracker.get_status()
if status["soft_cap_breached"]:
    # Handle soft-cap repair
    pass
```

### Guarantees

✅ **Coh_t ∈ [0, Coh_max] for all t**
✅ **Automatic repair at soft threshold**
✅ **Escalation at hard ceiling**
✅ **All projections auditable**

---

## 2. ASK Resolution Tracking (Clarity OS)

### Problem

Unresolved ASK (C-1 clarification requests) could accumulate indefinitely, leading to perpetual suspension without progress.

### Solution

Implemented **ASKResolutionTracker** that enforces monotonic progress through:

**State Transitions:**
```
Resolved ASK → ask_streak = 0
Unresolved ASK → ask_streak += 1
ask_streak ≥ 2 → light projection Π_t (drop low-confidence meanings)
ask_streak > 3 → auto-SILENCE + escalate (loop termination)
```

### Persistent ASK Repair

When `ask_streak ≥ 2`:
1. Drop lowest-confidence meanings from interpretation set I(c)
2. Reduce Coh by 0.03 (bounded at zero)
3. Invoke projection callback (if provided)
4. Log projection action for audit

### Timeout Progress Rule

When ASK times out:
- Select **safe default branch**
- **Do not** perform irreversible action
- Log decision as "timeout default"
- Mark for optional human review

Indefinite suspension is **forbidden**. Progress **must** be monotonic.

### Implementation

**Module:** `src/clarity_kernel/ask_resolution.py`

**Key Classes:**
- `ASKResolutionTracker`: Main ASK tracker
- `ASKEvent`: Individual ASK record
- `ASKResolutionStatus`: Enum (RESOLVED, UNRESOLVED, TIMEOUT, DEFAULTED)
- `ASKLoopViolation`: Exception for loop termination
- `ProjectionAction`: Light projection record

**Usage:**
```python
from clarity_kernel import ASKResolutionTracker

tracker = ASKResolutionTracker(max_ask_streak=3)

# Issue ASK
ask_id = tracker.issue_ask(
    question="What is the target dosage?",
    timeout_seconds=60
)

# Resolve ASK
tracker.resolve_ask(ask_id, response="50mg")
# -> ask_streak = 0 (monotonic progress restored)

# Or timeout with safe default
tracker.timeout_ask(ask_id, default_branch="request_explicit_input")
# -> ask_streak += 1

# Loop termination
if tracker.ask_streak > 3:
    # Raises ASKLoopViolation
    # Auto-SILENCE + escalate to governance
    pass
```

### Guarantees

✅ **ask_streak bounded at max 3**
✅ **Automatic repair at streak ≥ 2**
✅ **Auto-SILENCE at streak > 3**
✅ **No infinite suspension**
✅ **All ASK events auditable**

---

## 3. Ledger Totality (Governance OS)

### Problem

Without comprehensive logging of all non-emit events (cannon fires), the audit trail had gaps that could hide critical governance decisions.

### Solution

Enhanced **AuditLogger** to enforce **ledger totality**: every cannon fire MUST be logged.

### Cannon Fire Events (New)

All of the following now have dedicated log methods:

| Event Type | Method | Description |
|------------|--------|-------------|
| `ASK_ISSUED` | `log_ask_issued()` | C-1 clarification request |
| `ASK_RESOLVED` | `log_ask_resolved()` | ASK answered by user |
| `ASK_UNRESOLVED` | `log_ask_unresolved()` | ASK not answered |
| `ASK_TIMEOUT` | `log_ask_timeout()` | ASK timed out, safe default taken |
| `SILENCE` | `log_silence()` | I-6 silence enforced |
| `PROJECTION` | `log_projection()` | Π_t coherence repair |
| `ROLLBACK` | `log_rollback()` | State rollback to k* prefix |
| `COHERENCE_VIOLATION` | `log_coherence_violation()` | Hard cap violation |
| `ASK_LOOP_TERMINATED` | `log_ask_loop_terminated()` | Auto-SILENCE from loop |

### Ledger Entry Requirements

Every cannon fire log entry includes:
- **event_type**: Type of cannon fire
- **triggering_rule**: Rule that triggered event (e.g., "C-1", "I-6", "unAI_OS_hard_cap")
- **pre/post state hash**: Event ID and hash chain
- **timestamp**: Unix timestamp
- **resolution_status**: How event resolved
- **context**: Full event context for audit

### Implementation

**Module:** `src/clarity_kernel/logging.py` (enhanced)

**Usage:**
```python
from clarity_kernel import AuditLogger, EventType

logger = AuditLogger()

# Log ASK cannon fire
logger.log_ask_issued(
    ask_id="ask_1_1234567890",
    question="What is the file path?",
    kernel_state="EXECUTING"
)

# Log SILENCE cannon fire
logger.log_silence(
    variable_name="file_path",
    kernel_state="EXECUTING",
    reason="Guessing forbidden (I-6)"
)

# Log projection cannon fire
logger.log_projection(
    projection_type="minor",
    coh_before=0.55,
    coh_after=0.50,
    meanings_dropped=1,
    kernel_state="EXECUTING",
    reason="Soft-cap repair"
)

# Verify all cannon fires logged
cannon_fires = [
    EventType.ASK_ISSUED,
    EventType.SILENCE,
    EventType.PROJECTION,
    # ...
]
for event_type in cannon_fires:
    entries = logger.get_entries_by_type(event_type)
    assert len(entries) > 0, f"Cannon fire {event_type} not logged"
```

### Guarantees

✅ **Every cannon fire logged**
✅ **Triggering rule documented**
✅ **Pre/post state hashed**
✅ **Complete audit trail**
✅ **No silent events**

---

## 4. Rollback Depth Management (Governance OS)

### Problem

Without formal rollback depth rules, state recovery could discard too much valid history or preserve invalid state.

### Solution

Implemented **rollback depth rule** that preserves verified history:

**Rollback Rule:**
```
On UNSAT or eject:
  Let k* = last verified good prefix
  Roll back to max(0, k* - 2)
```

Where:
- `k*`: Event ID of last known-good state
- `k* - 2`: Safety margin (preserves 2 valid events before failure)
- `max(0, ...)`: Never roll back before genesis

### Safety Margin

The 2-event safety margin ensures:
1. Rollback doesn't discard valid work immediately before failure
2. System can recover context leading to failure
3. Audit trail preserves decision chain

### Implementation

**Logging:** `logger.log_rollback()` documents:
- `rollback_to_event_id`: Target event ID (k* - 2)
- `rollback_depth`: Number of events discarded
- `reason`: Human-readable reason for rollback

**Usage:**
```python
# On UNSAT detection
k_star = find_last_verified_good_prefix()  # e.g., event_id = 10
rollback_to = max(0, k_star - 2)  # 8
rollback_depth = current_event_id - rollback_to

logger.log_rollback(
    rollback_to_event_id=rollback_to,
    rollback_depth=rollback_depth,
    kernel_state="ABNORMAL",
    reason="UNSAT detected at event_id=12"
)

# Restore state to event_id = 8
restore_state_to(rollback_to)
```

### Guarantees

✅ **Valid history preserved (k* - 2)**
✅ **All rollbacks logged**
✅ **Never rolls back before genesis**
✅ **Audit trail intact**

---

## 5. Loop Termination Guarantees (Meta-Framework)

### Problem

Unresolved ASK loops could theoretically continue indefinitely, violating monotonic progress.

### Solution

Implemented **loop termination rule**:

```
If unresolved_C1_streak > 3:
  1. Auto-SILENCE
  2. Escalate to human authority
  3. Freeze optimization until resolved
```

### Detection

`ASKResolutionTracker` raises `ASKLoopViolation` when:
- `ask_streak` reaches `max_ask_streak` (default: 3)
- Next `issue_ask()` call triggers exception

### Response

On `ASKLoopViolation`:
1. Log `ASK_LOOP_TERMINATED` event
2. Trigger auto-SILENCE (I-6 enforcement)
3. Escalate to human authority (governance)
4. Freeze optimization until human resolves

### Implementation

```python
from clarity_kernel import ASKResolutionTracker, ASKLoopViolation

tracker = ASKResolutionTracker(max_ask_streak=3)

try:
    # This will raise if ask_streak ≥ 3
    ask_id = tracker.issue_ask("Clarify parameter X?")
except ASKLoopViolation as e:
    # Auto-SILENCE triggered
    logger.log_ask_loop_terminated(
        ask_streak=e.ask_streak,
        max_streak=e.max_streak,
        kernel_state="ESCALATED"
    )
    # Escalate to human authority
    escalate_to_governance()
```

### Guarantees

✅ **ASK loops terminate at streak > 3**
✅ **Auto-SILENCE enforced**
✅ **Escalation to governance**
✅ **No infinite loops**

---

## 6. Simulation Gate (Meta-Framework)

### Problem

Needed ability to distinguish prototype/simulation mode from production-strict mode.

### Solution

Added **simulation gate** with two modes:

**PROTOTYPE_SIM mode:**
- Partial or probabilistic resolution MAY be simulated
- Useful for development, testing, demos
- All simulated events MUST be logged with `simulated=True` flag

**PROD_STRICT mode:**
- Simulated resolution is **forbidden**
- Only verified, deterministic resolution allowed
- Production deployment mode

### Implementation

```python
from clarity_kernel import TemporalCoherenceTracker

# PROTOTYPE_SIM mode
tracker = TemporalCoherenceTracker()
tracker.mode = "PROTOTYPE_SIM"

if tracker.mode == "PROTOTYPE_SIM":
    # Allowed: simulate projection for testing
    simulated_projection = simulate_projection()
    logger.log_projection(..., context={"simulated": True})

# PROD_STRICT mode
tracker.mode = "PROD_STRICT"

if tracker.mode == "PROD_STRICT":
    # Forbidden: no simulation allowed
    if is_simulation:
        raise ValueError("Simulated resolution forbidden in PROD_STRICT mode")
```

### Guarantees

✅ **Clear mode distinction**
✅ **Simulated events flagged**
✅ **Production safety enforced**

---

## Integration Example

Complete example integrating all patch components:

```python
from clarity_kernel import (
    ClarityKernel,
    TemporalCoherenceTracker,
    ASKResolutionTracker,
    AuditLogger,
)

# Initialize kernel
kernel = ClarityKernel()
logger = AuditLogger()

# Initialize patch v1.1 components
coherence_tracker = TemporalCoherenceTracker(
    coh_soft=0.5,
    coh_max=1.0
)

ask_tracker = ASKResolutionTracker(
    max_ask_streak=3,
    projection_callback=lambda proj: logger.log_projection(
        projection_type=proj.projection_type,
        coh_before=proj.coh_before,
        coh_after=proj.coh_after,
        meanings_dropped=proj.meanings_dropped,
        kernel_state="EXECUTING",
        reason=proj.reason
    )
)

# Reasoning loop
for step in range(100):
    # Update temporal coherence
    drift = compute_drift(...)
    coherence_tracker.step(drift_delta=drift, lambda_param=1.0)

    # Check coherence violations
    if coherence_tracker.state.coh_t >= coherence_tracker.state.coh_max:
        logger.log_coherence_violation(
            coherence=coherence_tracker.state.coh_t,
            max_coherence=coherence_tracker.state.coh_max,
            kernel_state="ESCALATED"
        )
        # Escalate to governance
        break

    # Handle ambiguity
    if is_ambiguous:
        try:
            ask_id = ask_tracker.issue_ask(
                question="Clarify parameter X?",
                timeout_seconds=60
            )
            logger.log_ask_issued(ask_id, "Clarify parameter X?", "EXECUTING")

            # Wait for response or timeout
            response = wait_for_response(ask_id, timeout=60)

            if response:
                ask_tracker.resolve_ask(ask_id, response)
                logger.log_ask_resolved(ask_id, "Clarify parameter X?", response, "EXECUTING")
            else:
                ask_tracker.timeout_ask(ask_id, "request_explicit_input")
                logger.log_ask_timeout(ask_id, "Clarify parameter X?", "request_explicit_input", "EXECUTING")

        except ASKLoopViolation as e:
            logger.log_ask_loop_terminated(e.ask_streak, e.max_streak, "ESCALATED")
            # Auto-SILENCE + escalate
            logger.log_silence("parameter_x", "ESCALATED", "ASK loop terminated")
            break

# Verify ledger totality
assert logger.has_violations() or len(logger.get_all_entries()) > 0
```

---

## Verification Checklist

| Component | Status | Tests |
|-----------|--------|-------|
| Temporal Coherence Tracking | ✅ | `test_temporal_coherence.py` |
| ASK Resolution Tracking | ✅ | `test_ask_resolution.py` |
| Ledger Totality | ✅ | `test_logging.py` (enhanced) |
| Rollback Depth | ✅ | `test_rollback.py` |
| Loop Termination | ✅ | `test_ask_resolution.py` |
| Simulation Gate | ✅ | `test_temporal_coherence.py` |

---

## Migration Guide

### For Existing Code

**No breaking changes.** Patch v1.1 is fully backwards-compatible.

**Optional adoption:**
- Temporal coherence tracking is opt-in (import and use `TemporalCoherenceTracker`)
- ASK resolution tracking is opt-in (import and use `ASKResolutionTracker`)
- New cannon fire logging methods are additions (existing log methods unchanged)

**Recommended:**
1. Add temporal coherence tracking to long-running reasoning loops
2. Add ASK resolution tracking to ambiguity handling
3. Use new cannon fire logging methods for complete audit trail

### For New Code

**Start with:**
```python
from clarity_kernel import (
    ClarityKernel,
    TemporalCoherenceTracker,
    ASKResolutionTracker,
    AuditLogger,
)

kernel = ClarityKernel()
coherence = TemporalCoherenceTracker()
ask_tracker = ASKResolutionTracker()
logger = AuditLogger()
```

---

## Effect

After Kernel Patch v1.1:

✅ **Temporal coherence cannot snowball**
✅ **Ambiguity cannot stall indefinitely**
✅ **ASK loops self-heal before silence**
✅ **Rollbacks preserve valid history**
✅ **All non-emits are auditable**
✅ **Adversarial ambiguity is capped**

**This amendment is binding and effective immediately.**

---

## Appendix: Formal Specifications

### A.1 Temporal Coherence Update Rule

```
Coh_{t+1} = clip[0, Coh_max](Coh_t + Δ_drift(t) - δ_decay(λ, state))

where:
  Δ_drift(t): Change in coherence at step t
  δ_decay(λ, state): Per-step decay function
  λ ∈ [1.0, 2.0]: Decay scaling parameter
  state_complexity ∈ [1.0, 10.0]: State complexity metric

δ_decay(λ, state) = δ_min + (δ_max - δ_min) * min(1.0, state_complexity / 10.0) * λ

Soft-cap repair:
  if Coh_{t+1} > Coh_soft:
    Π_t: minor projection
    Coh_{t+1} := max(0, Coh_{t+1} - 0.05)

Hard-cap escalation:
  if Coh_{t+1} ≥ Coh_max:
    raise CoherenceViolation
    escalate to governance
```

### A.2 ASK Resolution State Machine

```
States:
  - PENDING: ASK issued, awaiting response
  - RESOLVED: Response received, ask_streak = 0
  - UNRESOLVED: No response, ask_streak += 1
  - TIMEOUT: Timeout reached, safe default taken
  - TERMINATED: Loop terminated, auto-SILENCE

Transitions:
  PENDING → RESOLVED: user provides response
    → ask_streak = 0

  PENDING → UNRESOLVED: no response within reasonable time
    → ask_streak += 1
    → if ask_streak ≥ 2: trigger persistent_ask_repair()

  PENDING → TIMEOUT: timeout_seconds elapsed
    → ask_streak += 1
    → select safe_default_branch
    → if ask_streak ≥ 2: trigger persistent_ask_repair()

  any → TERMINATED: ask_streak > max_ask_streak
    → raise ASKLoopViolation
    → auto-SILENCE
    → escalate to governance
```

### A.3 Rollback Depth Calculation

```
Given:
  k*: Last verified good prefix (event_id)
  n: Safety margin (default: 2)

Rollback target:
  rollback_to = max(0, k* - n)

Rollback depth:
  depth = current_event_id - rollback_to

Constraints:
  rollback_to ≥ 0 (never before genesis)
  k* verified (via hash chain or external verification)
  n ≥ 1 (preserve at least 1 event before failure)
```

---

**END OF KERNEL PATCH v1.1**
