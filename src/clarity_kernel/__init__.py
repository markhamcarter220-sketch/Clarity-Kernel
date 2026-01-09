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

__version__ = "1.2.0"

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
    TokenValidationError,
    AttentionInvariantViolation,
    TruthInvariantViolation,
    LoggingInvariantViolation,
    SilenceInvariantViolation,
    ComplexityInvariantViolation,
    WCountingFraudViolation,
    validate_clarity,
    validate_authority,
    validate_attention,
    validate_truth,
    validate_logging,
    validate_silence,
    validate_complexity,
    # Authority token validation
    register_trusted_issuer,
    is_trusted_issuer,
    check_nonce_replay,
    check_scope_hierarchy,
    verify_token_signature,
    validate_token_expiry,
    MAX_TOKEN_AGE,
    TRUSTED_ISSUER_REGISTRY,
    # W-counting fraud detection
    detect_variable_bundling,
    detect_probabilistic_collapse,
    validate_material_classification,
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
    ChainIntegrityViolation,
    get_default_logger,
    set_default_logger,
)

# AIL (Adaptive Interaction Layer) - Non-Normative
from .ail import (
    AILSession,
    AILWrapper,
    AILInterferenceViolation,
    TERMINAL_AMBIGUITY_TEXT,
    AIL_PERMITTED_ACTIONS,
    AIL_FORBIDDEN_ACTIONS,
)

# LTC (Legitimate Transfer Constraint)
from .ltc import (
    LTCEnforcer,
    LTCVerdict,
    LTCViolation,
    LTCEvaluation,
    Domain,
    TransferRequest,
    check_domain_transfer,
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
    "TokenValidationError",
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
    # Authority token validation
    "register_trusted_issuer",
    "is_trusted_issuer",
    "check_nonce_replay",
    "check_scope_hierarchy",
    "verify_token_signature",
    "validate_token_expiry",
    "MAX_TOKEN_AGE",
    "TRUSTED_ISSUER_REGISTRY",
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
    "ChainIntegrityViolation",
    "get_default_logger",
    "set_default_logger",
    # AIL (Non-Normative)
    "AILSession",
    "AILWrapper",
    "TERMINAL_AMBIGUITY_TEXT",
    # LTC
    "LTCEnforcer",
    "LTCVerdict",
    "LTCViolation",
    "LTCEvaluation",
    "Domain",
    "TransferRequest",
    "check_domain_transfer",
]
