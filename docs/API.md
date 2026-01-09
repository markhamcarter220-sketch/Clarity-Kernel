# API Reference
## Clarity Kernel v1.2.0 — Method Signatures and Types

**Version:** 1.0
**Framework Version:** Clarity Kernel v1.2.0
**Status:** Normative Reference

---

## Table of Contents

1. [Core SSL Module](#core-ssl-module)
2. [Invariants Module](#invariants-module)
3. [State Machine Module](#state-machine-module)
4. [Control Modes Module](#control-modes-module)
5. [Logging Module](#logging-module)
6. [LTC Module](#ltc-module)
7. [Exception Hierarchy](#exception-hierarchy)

---

## Core SSL Module

**Import:** `from clarity_kernel import ClarityKernel, PermissionRequest, PermissionResponse`

### ClarityKernel

The main enforcement engine that validates invariants, manages state transitions, and makes permission-to-proceed decisions.

#### Constructor

```python
def __init__(
    self,
    logger: Optional[AuditLogger] = None,
    max_width: int = 3,
    ssl_version: str = "v1.2.0"
) -> None
```

**Parameters:**
- `logger` (Optional[AuditLogger]): Audit logger instance. Uses default logger if None.
- `max_width` (int): Maximum interface width (default 3 per spec).
- `ssl_version` (str): SSL version string (must match spec version).

**Example:**
```python
from clarity_kernel import ClarityKernel, get_default_logger

kernel = ClarityKernel(
    logger=get_default_logger(),
    max_width=3,
    ssl_version="v1.2.0"
)
```

#### request_permission()

Main entry point for permission-to-proceed decisions.

```python
def request_permission(
    self,
    request: PermissionRequest
) -> PermissionResponse
```

**Parameters:**
- `request` (PermissionRequest): The permission request containing all required context.

**Returns:**
- `PermissionResponse`: Decision with granted status, control mode, and execution guard.

**Raises:**
- `PermissionDenied`: If any invariant is violated.
- `ImmediateStopTriggered`: If immediate stop condition is met.

**Invariant Validation Order:**
1. I-1 (Clarity): Validates required definitions, thresholds, constraints
2. I-7 (Complexity): Measures interface width w
3. I-2 (Authority): Validates authority token
4. I-3 (Attention): Validates continuous attention requirements
5. I-6 (Silence): Ensures no guessing
6. I-4 (Truth): Ensures all invariants satisfied before claiming ALLOWED
7. I-5 (Logging): Ensures all events logged

**Example:**
```python
request = PermissionRequest(
    operation_id="read_file_001",
    variables=[
        Variable("file_path", resolved=True, material=True, value="/etc/config.yaml")
    ],
    required_definitions={"file_path": "/etc/config.yaml"},
    required_thresholds={},
    required_constraints=["file_exists", "read_permission"],
    authority=authority_token,
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
    print(f"Permission granted: {response.control_mode}")
    # Execute with guard...
```

#### apply_override()

Applies break-glass override for ABNORMAL mode operation.

```python
def apply_override(
    self,
    override_signature: str,
    unsatisfiable_invariants: list[str],
    justification: str
) -> None
```

**Parameters:**
- `override_signature` (str): Human authorization signature (non-empty, verifiable).
- `unsatisfiable_invariants` (list[str]): Which invariants cannot be satisfied (e.g., `["I-1", "I-7"]`).
- `justification` (str): Reason for override (logged immutably).

**Raises:**
- `ValueError`: If override_signature is invalid.

**Side Effects:**
- Transitions operating mode to ABNORMAL
- Sets `override_active = True`
- Logs override event

**Example:**
```python
kernel.apply_override(
    override_signature="admin_alice_2026-01-08T10:30:00Z",
    unsatisfiable_invariants=["I-1"],
    justification="Emergency: sensor data ambiguous, manual inspection confirms safety"
)
```

#### trigger_immediate_stop()

Triggers immediate stop (halts execution and reasoning immediately).

```python
def trigger_immediate_stop(
    self,
    reason: str,
    triggered_by: str
) -> None
```

**Parameters:**
- `reason` (str): Why stop was triggered.
- `triggered_by` (str): What triggered the stop (component or condition).

**Raises:**
- `ImmediateStopTriggered`: Always (this method never returns normally).

**Stop Semantics:**
- Execution halts immediately
- Reasoning halts immediately
- No automatic retry
- No partial completion
- No background continuation

**Example:**
```python
try:
    kernel.trigger_immediate_stop(
        reason="Deadman switch lost",
        triggered_by="continuous_authorization_guard"
    )
except ImmediateStopTriggered as e:
    print(f"STOP: {e.trigger} - {e}")
    # Handle graceful shutdown...
```

#### reset()

Resets the kernel to IDLE state.

```python
def reset(self) -> None
```

**Preconditions:**
- Current state must be COMPLETE or RETURN_TO_SAFE_STATE

**Raises:**
- `ValueError`: If called from invalid state.

**Example:**
```python
# After operation completes
if kernel.state_machine.current_state == KernelState.COMPLETE:
    kernel.reset()
```

---

### PermissionRequest

Request for permission to proceed with an operation.

**Import:** `from clarity_kernel import PermissionRequest`

#### Structure

```python
@dataclass
class PermissionRequest:
    operation_id: str
    variables: list[Variable]
    required_definitions: dict[str, Any]
    required_thresholds: dict[str, Any]
    required_constraints: list[str]
    authority: Optional[AuthorityToken]
    required_scope: str
    preconditions: MomentaryPreconditions
    triggers: ContinuousTriggers
    requires_continuous_attention: bool
    harm_scenario: str
```

#### Field Specifications

**operation_id** (str)
- Unique identifier for this operation
- Used for logging and correlation
- Must be non-empty

**variables** (list[Variable])
- All variables in the constraint system
- Used to compute interface width w
- Each variable must specify: name, resolved, material, value

**required_definitions** (dict[str, Any])
- Definitions required for I-1 (Clarity)
- Keys: definition names
- Values: concrete values (not ambiguous)

**required_thresholds** (dict[str, Any])
- Thresholds required for I-1 (Clarity)
- Keys: threshold names
- Values: numeric thresholds

**required_constraints** (list[str])
- Constraints required for I-1 (Clarity)
- Each constraint must be explicitly stated

**authority** (Optional[AuthorityToken])
- Authorization token for I-2 (Authority)
- None triggers AuthorityInvariantViolation
- Must have valid signature and scope

**required_scope** (str)
- Scope of authority required
- Hierarchical dot notation (e.g., "file.read", "medical.prescribe")
- Matched against authority.scope

**preconditions** (MomentaryPreconditions)
- Preconditions for momentary authorization
- All must be True for momentary mode

**triggers** (ContinuousTriggers)
- Triggers for continuous authorization
- Any True requires continuous mode

**requires_continuous_attention** (bool)
- Whether continuous human attention required
- If True and triggers not satisfied, triggers I-3 violation

**harm_scenario** (str)
- Description of potential harm if executed without attention
- Required for I-3 (Attention) validation

---

### PermissionResponse

Response to a permission request.

**Import:** `from clarity_kernel import PermissionResponse`

#### Structure

```python
@dataclass
class PermissionResponse:
    granted: bool
    control_mode: Optional[ControlMode]
    execution_guard: Optional[Any]  # MomentaryExecutionGuard | ContinuousExecutionGuard
    kernel_state: KernelState
    measured_w: int
    satisfied_invariants: set[str]
    denial_reason: Optional[str] = None
```

#### Field Specifications

**granted** (bool)
- Whether permission is granted
- True only if ALL invariants satisfied

**control_mode** (Optional[ControlMode])
- Required control mode if granted
- Either ControlMode.MOMENTARY or ControlMode.CONTINUOUS
- None if not granted

**execution_guard** (Optional[Any])
- Guard object for execution
- MomentaryExecutionGuard for momentary mode
- ContinuousExecutionGuard for continuous mode
- None if not granted

**kernel_state** (KernelState)
- Current kernel state after evaluation
- See State Machine Module for states

**measured_w** (int)
- Measured interface width
- Count of unresolved material variables

**satisfied_invariants** (set[str])
- Set of satisfied invariant IDs
- Example: {"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"}

**denial_reason** (Optional[str])
- Reason for denial if not granted
- None if granted

---

## Invariants Module

**Import:** `from clarity_kernel import Variable, AuthorityToken, validate_*`

### Variable

Represents a variable in the constraint system.

```python
@dataclass(frozen=True)
class Variable:
    name: str
    resolved: bool
    material: bool
    value: Optional[Any] = None
```

**Field Specifications:**

**name** (str)
- Variable identifier
- Must be non-empty

**resolved** (bool)
- Whether the value is known
- If True, value must not be None

**material** (bool)
- Whether the variable materially affects permission decision
- See docs/VARIABLES.md for classification guide
- Material variables count toward interface width w

**value** (Optional[Any])
- The resolved value
- Must be None if resolved=False
- Must not be None if resolved=True

**Example:**
```python
# Material resolved variable
file_path = Variable(
    name="file_path",
    resolved=True,
    material=True,
    value="/etc/config.yaml"
)

# Material unresolved variable (counts toward w)
dosage = Variable(
    name="dosage_mg",
    resolved=False,
    material=True,
    value=None
)

# Non-material variable (does not count toward w)
request_id = Variable(
    name="request_id",
    resolved=True,
    material=False,
    value="req_12345"
)
```

---

### AuthorityToken

Authorization token for I-2 (Authority Invariant).

```python
@dataclass
class AuthorityToken:
    source: str           # Identity of authorizing entity
    verifiable: bool      # DEPRECATED - use signature verification
    scope: str            # Scope of authorization
    signature: bytes      # Ed25519 signature (64 bytes)
    timestamp: int        # Unix timestamp of issuance
    nonce: bytes          # Random nonce (32 bytes)
    issuer_pubkey: bytes  # Public key of issuer (32 bytes)
```

**See docs/AUTHORITY.md for complete specification.**

**Example:**
```python
authority_token = AuthorityToken(
    source="admin_alice",
    verifiable=True,  # DEPRECATED, ignored
    scope="file.read",
    signature=b'...',  # 64 bytes Ed25519 signature
    timestamp=1704067200,
    nonce=os.urandom(32),
    issuer_pubkey=b'...'  # 32 bytes public key
)
```

---

### Validation Functions

#### validate_clarity()

Validates I-1 (Clarity Invariant).

```python
def validate_clarity(
    required_definitions: dict[str, Any],
    required_thresholds: dict[str, Any],
    required_constraints: list[str]
) -> None
```

**Raises:**
- `ClarityInvariantViolation`: If any required element is ambiguous or missing.

---

#### validate_authority()

Validates I-2 (Authority Invariant).

```python
def validate_authority(
    authority: Optional[AuthorityToken],
    required_scope: str
) -> None
```

**Raises:**
- `AuthorityInvariantViolation`: If authority is None, scope insufficient, or signature invalid.

---

#### validate_attention()

Validates I-3 (Attention Invariant).

```python
def validate_attention(
    requires_continuous_attention: bool,
    continuous_mode_active: bool,
    harm_scenario: str
) -> None
```

**Raises:**
- `AttentionInvariantViolation`: If continuous attention required but not provided.

---

#### validate_truth()

Validates I-4 (Truth Invariant).

```python
def validate_truth(
    satisfied_invariants: set[str],
    all_invariants: set[str],
    claiming_allowed: bool
) -> None
```

**Raises:**
- `TruthInvariantViolation`: If claiming ALLOWED while any invariant unsatisfied.

---

#### validate_logging()

Validates I-5 (Logging Invariant).

```python
def validate_logging(
    event_logged: bool,
    event_type: str
) -> None
```

**Raises:**
- `LoggingInvariantViolation`: If event not logged.

---

#### validate_silence()

Validates I-6 (Silence Invariant).

```python
def validate_silence(
    variable: Variable,
    attempting_guess: bool
) -> None
```

**Raises:**
- `SilenceInvariantViolation`: If attempting to guess unresolved variable value.

---

#### validate_complexity()

Validates I-7 (Complexity Invariant).

```python
def validate_complexity(
    variables: list[Variable],
    max_width: int
) -> int
```

**Returns:**
- `int`: Measured interface width w (count of unresolved material variables).

**Raises:**
- `ComplexityInvariantViolation`: If w > max_width.

**Example:**
```python
variables = [
    Variable("file_path", resolved=True, material=True, value="/etc/config.yaml"),
    Variable("dosage_mg", resolved=False, material=True, value=None),
    Variable("request_id", resolved=True, material=False, value="req_123"),
]

w = validate_complexity(variables, max_width=3)
# w = 1 (only dosage_mg is unresolved and material)
```

---

## State Machine Module

**Import:** `from clarity_kernel import KernelState, OperatingMode, ClarityStateMachine`

### KernelState

All possible kernel states.

```python
class KernelState(Enum):
    # Normal mode states
    IDLE = "IDLE"
    PRECONDITIONS_VALID = "PRECONDITIONS_VALID"
    WIDTH_OK = "WIDTH_OK"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"

    # Continuous authorization mode states
    CONTINUOUS_AUTH_REQUIRED = "CONTINUOUS_AUTH_REQUIRED"
    IMMEDIATE_STOP = "IMMEDIATE_STOP"

    # Abnormal/override mode states
    INVARIANT_UNSATISFIABLE = "INVARIANT_UNSATISFIABLE"
    EXPLICIT_HUMAN_OVERRIDE = "EXPLICIT_HUMAN_OVERRIDE"
    ABNORMAL_EXECUTION = "ABNORMAL_EXECUTION"
    PERSISTENT_WARNING = "PERSISTENT_WARNING"
    RESOLUTION = "RESOLUTION"
    RETURN_TO_SAFE_STATE = "RETURN_TO_SAFE_STATE"

    # Degraded mode state
    READ_ONLY = "READ_ONLY"
```

---

### OperatingMode

High-level operating modes.

```python
class OperatingMode(Enum):
    NORMAL = "NORMAL"
    CONTINUOUS = "CONTINUOUS"
    ABNORMAL = "ABNORMAL"
    DEGRADED = "DEGRADED"
```

---

### ClarityStateMachine

State machine controller.

#### current_state

```python
@property
def current_state(self) -> KernelState
```

**Returns:** Current kernel state.

---

## Control Modes Module

**Import:** `from clarity_kernel import ControlMode, MomentaryPreconditions, ContinuousTriggers`

### ControlMode

Control modes for authorization.

```python
class ControlMode(Enum):
    MOMENTARY = "momentary"    # Single authorization allows full execution
    CONTINUOUS = "continuous"  # Ongoing confirmation required (deadman switch)
```

---

### MomentaryPreconditions

Preconditions for momentary authorization (ALL must be True).

```python
@dataclass(frozen=True)
class MomentaryPreconditions:
    outcome_reversible: bool              # Can the outcome be undone?
    risk_does_not_increase: bool          # Does risk remain constant over time?
    no_new_critical_info: bool            # Can critical info emerge during execution?
    w_within_limit: bool                  # Is w ≤ 3 at authorization time?
    execution_window_bounded: bool        # Is execution time short and bounded?
```

#### Methods

**all_satisfied() -> bool**
- Returns True only if ALL preconditions are satisfied

**get_failed_conditions() -> list[str]**
- Returns list of condition names that are not satisfied

---

### ContinuousTriggers

Triggers for continuous authorization (ANY True requires continuous mode).

```python
@dataclass(frozen=True)
class ContinuousTriggers:
    outcome_irreversible: bool            # Is the outcome permanent?
    compliance_safety_exposure: bool      # Are there compliance/safety concerns?
    context_may_change: bool              # Can context change during execution?
    ambiguity_at_initiation: bool         # Does ambiguity exist at start?
    w_may_fluctuate: bool                 # Can w change during execution?
    execution_window_extended: bool       # Is execution time long?
```

#### Methods

**any_triggered() -> bool**
- Returns True if ANY trigger condition is met

**get_triggered_conditions() -> list[str]**
- Returns list of condition names that are triggered

---

### determine_control_mode()

Determines required control mode.

```python
def determine_control_mode(
    preconditions: MomentaryPreconditions,
    triggers: ContinuousTriggers
) -> ControlMode
```

**Returns:**
- `ControlMode.CONTINUOUS` if any trigger is met
- `ControlMode.MOMENTARY` otherwise

---

## Logging Module

**Import:** `from clarity_kernel import AuditLogger, LogEntry, EventType, get_default_logger`

### AuditLogger

Immutable append-only audit logger.

#### log_authorization()

```python
def log_authorization(
    self,
    granted: bool,
    authority_source: str,
    required_scope: str,
    kernel_state: str,
    control_mode: str,
    context: Optional[dict[str, Any]] = None
) -> None
```

#### log_invariant_violation()

```python
def log_invariant_violation(
    self,
    invariant_id: str,
    kernel_state: str,
    reason: str,
    context: Optional[dict[str, Any]] = None
) -> None
```

#### log_width_evaluation()

```python
def log_width_evaluation(
    self,
    measured_w: int,
    unresolved_variables: list[str],
    kernel_state: str,
    decomposition_status: DecompositionStatus,
    resolution_outcome: ResolutionOutcome,
    context: Optional[dict[str, Any]] = None
) -> None
```

#### log_override()

```python
def log_override(
    self,
    override_signature: str,
    unsatisfiable_invariants: list[str],
    kernel_state: str,
    context: Optional[dict[str, Any]] = None
) -> None
```

#### log_immediate_stop()

```python
def log_immediate_stop(
    self,
    reason: str,
    kernel_state: str,
    triggered_by: str,
    context: Optional[dict[str, Any]] = None
) -> None
```

#### log_state_transition()

```python
def log_state_transition(
    self,
    from_state: str,
    to_state: str,
    reason: str,
    invariants_evaluated: Optional[dict[str, bool]] = None,
    **kwargs
) -> None
```

---

### EventType

Event types for logging.

```python
class EventType(Enum):
    AUTHORIZATION = "authorization"
    INVARIANT_VIOLATION = "invariant_violation"
    WIDTH_EVALUATION = "width_evaluation"
    STATE_TRANSITION = "state_transition"
    OVERRIDE = "override"
    IMMEDIATE_STOP = "immediate_stop"
    LTC_TRANSFER_EVALUATED = "ltc_transfer_evaluated"
```

---

### get_default_logger()

Returns default logger instance.

```python
def get_default_logger() -> AuditLogger
```

---

## LTC Module

**Import:** `from clarity_kernel import LTCEnforcer, LTCVerdict, Domain, TransferRequest`

### LTCEnforcer

Legitimate Transfer Constraint enforcement engine.

#### evaluate()

Evaluates domain transfer request.

```python
def evaluate(
    self,
    transfer: TransferRequest
) -> LTCEvaluation
```

**Returns:**
- `LTCEvaluation` with verdict (ALLOW, DENY, SILENCE)

**Example:**
```python
enforcer = LTCEnforcer()

source = Domain(
    name="medical.dosage",
    invariants=["patient_weight_known", "drug_interaction_checked"],
    context={"domain_type": "medical"}
)

target = Domain(
    name="medical.prescription",
    invariants=["patient_weight_known", "drug_interaction_checked"],
    context={"domain_type": "medical"}
)

transfer = TransferRequest(
    source_domain=source,
    target_domain=target,
    logic_framework="dosage_calculation",
    proposed_mapping={
        "patient_weight_known": "patient_weight_known",
        "drug_interaction_checked": "drug_interaction_checked"
    }
)

evaluation = enforcer.evaluate(transfer)

if evaluation.verdict == LTCVerdict.ALLOW:
    print("Transfer allowed")
elif evaluation.verdict == LTCVerdict.DENY:
    print(f"Transfer denied: {evaluation.reason_codes}")
else:
    print("Insufficient information (SILENCE)")
```

---

### LTCVerdict

Verdict for domain transfer attempt.

```python
class LTCVerdict(Enum):
    ALLOW = "allow"      # Explicit invariant-preserving mapping proven
    DENY = "deny"        # Invariant preservation fails
    SILENCE = "silence"  # Insufficient information
```

---

### Domain

Represents a reasoning domain with explicit boundaries.

```python
@dataclass
class Domain:
    name: str
    invariants: List[str]       # Required structural invariants
    context: Dict[str, Any]     # Domain-specific context
```

---

### TransferRequest

Request to transfer logic from source domain to target domain.

```python
@dataclass
class TransferRequest:
    source_domain: Domain
    target_domain: Domain
    logic_framework: str                           # Explicit description
    proposed_mapping: Optional[Dict[str, Any]]     # Explicit invariant mapping
```

---

### check_domain_transfer()

Convenience function for domain transfer checking.

```python
def check_domain_transfer(
    source_domain: Domain,
    target_domain: Domain,
    logic_framework: str,
    proposed_mapping: Optional[Dict[str, Any]] = None
) -> LTCEvaluation
```

---

## Exception Hierarchy

### SSL Exceptions

```python
class PermissionDenied(Exception):
    """Raised when permission to proceed is denied."""
    reason: str
    kernel_state: str

class ImmediateStopTriggered(Exception):
    """Raised when immediate stop is triggered."""
    trigger: str
```

### Invariant Violations

```python
class InvariantViolation(Exception):
    """Base class for all invariant violations."""
    invariant_id: str
    context: dict[str, Any]

class ClarityInvariantViolation(InvariantViolation):
    """I-1: Clarity Invariant violation."""
    ambiguous_elements: list[str]

class AuthorityInvariantViolation(InvariantViolation):
    """I-2: Authority Invariant violation."""
    required_authority: str

class AttentionInvariantViolation(InvariantViolation):
    """I-3: Attention Invariant violation."""
    harm_scenario: str

class TruthInvariantViolation(InvariantViolation):
    """I-4: Truth Invariant violation."""
    unsatisfied_invariants: list[str]

class LoggingInvariantViolation(InvariantViolation):
    """I-5: Logging Invariant violation."""
    suppression_attempt: str

class SilenceInvariantViolation(InvariantViolation):
    """I-6: Silence Invariant violation."""
    guessed_value: Any
    variable_name: str

class ComplexityInvariantViolation(InvariantViolation):
    """I-7: Complexity Invariant violation."""
    measured_w: int
    unresolved_variables: list[str]
```

### State Machine Exceptions

```python
class InvalidStateTransition(Exception):
    """Raised when invalid state transition is attempted."""
    from_state: KernelState
    to_state: KernelState
    reason: str

class SilentTransitionAttempt(Exception):
    """Raised when state transition attempted without logging."""
    from_state: KernelState
    to_state: KernelState
```

### Control Mode Exceptions

```python
class ControlModeViolation(Exception):
    """Base class for control mode violations."""

class MomentaryAuthorizationForbidden(ControlModeViolation):
    """Raised when momentary authorization preconditions not met."""
    failed_conditions: list[str]

class ContinuousAuthorizationLost(ControlModeViolation):
    """Raised when continuous authorization confirmation lost."""
    lost_at: datetime

class ContinuousAuthorizationRequired(ControlModeViolation):
    """Raised when continuous mode required but momentary attempted."""
    triggering_conditions: list[str]
```

### LTC Exceptions

```python
class LTCViolation(Exception):
    """Raised when illegitimate domain transfer attempted."""
    reason: str
    context: dict[str, Any]
```

---

## Version History

**v1.0 (2026-01-08):**
- Initial API reference for Clarity Kernel v1.2.0
- Complete type signatures for all public APIs
- Exception hierarchy documentation
- Method parameter specifications

---

**End of API Reference**
