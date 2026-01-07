"""
Clarity Kernel — Safety-Critical Reasoning Governance Framework

The Clarity Kernel is a governance framework that enforces when reasoning,
decisions, or actions are permitted to proceed.

Main components:
- SSL (Stable Structural Layer): Main kernel enforcement engine
- Invariants: Seven hard invariants that must be satisfied
- State Machine: State transitions for Normal, Continuous, and Abnormal modes
- Control Modes: Momentary and Continuous authorization
- Logging: Immutable audit logging

Usage:
    from clarity_kernel import ClarityKernel, PermissionRequest, Variable, AuthorityToken
    from clarity_kernel import MomentaryPreconditions, ContinuousTriggers

    kernel = ClarityKernel()
    request = PermissionRequest(...)
    response = kernel.request_permission(request)
"""

__version__ = "1.1.0"

# Core SSL
from .ssl import (
    ClarityKernel,
    PermissionRequest,
    PermissionResponse,
    PermissionDenied,
    ImmediateStopTriggered,
)

# Invariants
from .invariants import (
    Variable,
    AuthorityToken,
    InvariantViolation,
    ClarityInvariantViolation,
    AuthorityInvariantViolation,
    AttentionInvariantViolation,
    TruthInvariantViolation,
    LoggingInvariantViolation,
    SilenceInvariantViolation,
    ComplexityInvariantViolation,
    validate_clarity,
    validate_authority,
    validate_attention,
    validate_truth,
    validate_logging,
    validate_silence,
    validate_complexity,
)

# State Machine
from .state_machine import (
    KernelState,
    OperatingMode,
    ClarityStateMachine,
    StateMachineContext,
    InvalidStateTransition,
    SilentTransitionAttempt,
)

# Control Modes
from .control_modes import (
    ControlMode,
    MomentaryPreconditions,
    ContinuousTriggers,
    ContinuousConfirmation,
    MomentaryExecutionGuard,
    ContinuousExecutionGuard,
    MomentaryAuthorizationForbidden,
    ContinuousAuthorizationLost,
    ContinuousAuthorizationRequired,
    determine_control_mode,
)

# Logging
from .logging import (
    AuditLogger,
    LogEntry,
    EventType,
    ResolutionOutcome,
    DecompositionStatus,
    LogSuppressionAttempt,
    LogMutationAttempt,
    get_default_logger,
    set_default_logger,
)

# AIL (Adaptive Interaction Layer) - Non-Normative
from .ail import (
    AILSession,
    AILWrapper,
    AILResponse,
    AILResponseType,
)

__all__ = [
    # Core SSL
    "ClarityKernel",
    "PermissionRequest",
    "PermissionResponse",
    "PermissionDenied",
    "ImmediateStopTriggered",
    # Invariants
    "Variable",
    "AuthorityToken",
    "InvariantViolation",
    "ClarityInvariantViolation",
    "AuthorityInvariantViolation",
    "AttentionInvariantViolation",
    "TruthInvariantViolation",
    "LoggingInvariantViolation",
    "SilenceInvariantViolation",
    "ComplexityInvariantViolation",
    "validate_clarity",
    "validate_authority",
    "validate_attention",
    "validate_truth",
    "validate_logging",
    "validate_silence",
    "validate_complexity",
    # State Machine
    "KernelState",
    "OperatingMode",
    "ClarityStateMachine",
    "StateMachineContext",
    "InvalidStateTransition",
    "SilentTransitionAttempt",
    # Control Modes
    "ControlMode",
    "MomentaryPreconditions",
    "ContinuousTriggers",
    "ContinuousConfirmation",
    "MomentaryExecutionGuard",
    "ContinuousExecutionGuard",
    "MomentaryAuthorizationForbidden",
    "ContinuousAuthorizationLost",
    "ContinuousAuthorizationRequired",
    "determine_control_mode",
    # Logging
    "AuditLogger",
    "LogEntry",
    "EventType",
    "ResolutionOutcome",
    "DecompositionStatus",
    "LogSuppressionAttempt",
    "LogMutationAttempt",
    "get_default_logger",
    "set_default_logger",
    # AIL (Non-Normative)
    "AILSession",
    "AILWrapper",
    "AILResponse",
    "AILResponseType",
]
