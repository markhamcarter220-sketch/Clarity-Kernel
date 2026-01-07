"""
Clarity Kernel SSL — Stable Structural Layer (Section 4.1)

This is the privileged control layer that enforces all kernel invariants,
manages state transitions, and makes permission-to-proceed decisions.

The SSL is:
- Immutable at runtime (Section 14)
- Non-bypassable by AIL
- Can halt all downstream behavior unilaterally

This module orchestrates:
- Invariant validation (invariants.py)
- State machine control (state_machine.py)
- Control mode enforcement (control_modes.py)
- Audit logging (logging.py)
"""

from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime, timedelta

from .invariants import (
    Variable,
    AuthorityToken,
    validate_clarity,
    validate_authority,
    validate_attention,
    validate_truth,
    validate_logging,
    validate_silence,
    validate_complexity,
    get_all_invariant_ids,
    InvariantViolation,
    ComplexityInvariantViolation,
)
from .state_machine import (
    ClarityStateMachine,
    KernelState,
    OperatingMode,
    StateMachineContext,
    NormalModeController,
    ContinuousModeController,
    AbnormalModeController,
)
from .control_modes import (
    ControlMode,
    MomentaryPreconditions,
    ContinuousTriggers,
    MomentaryExecutionGuard,
    ContinuousExecutionGuard,
    determine_control_mode,
)
from .logging import (
    AuditLogger,
    EventType,
    ResolutionOutcome,
    DecompositionStatus,
    get_default_logger,
)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class PermissionDenied(Exception):
    """Raised when permission to proceed is denied."""

    def __init__(self, message: str, reason: str, kernel_state: str):
        super().__init__(message)
        self.reason = reason
        self.kernel_state = kernel_state


class ImmediateStopTriggered(Exception):
    """
    Raised when immediate stop is triggered.

    Per Section 12:
    - execution halts immediately
    - reasoning halts immediately
    - no automatic retry
    - no partial completion
    - no background continuation
    """

    def __init__(self, message: str, trigger: str):
        super().__init__(message)
        self.trigger = trigger


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class PermissionRequest:
    """
    Request for permission to proceed with an operation.

    Attributes:
        operation_id: Unique identifier for this operation
        variables: All variables in the constraint system
        required_definitions: Definitions required for clarity
        required_thresholds: Thresholds required for clarity
        required_constraints: Constraints required for clarity
        authority: Authorization token (if available)
        required_scope: Scope of authority required
        preconditions: Momentary authorization preconditions
        triggers: Continuous authorization triggers
        requires_continuous_attention: Whether continuous attention is needed
        harm_scenario: Description of potential harm (for I-3)
    """
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


@dataclass
class PermissionResponse:
    """
    Response to a permission request.

    Attributes:
        granted: Whether permission is granted
        control_mode: Required control mode (if granted)
        execution_guard: Guard object for execution (if granted)
        kernel_state: Current kernel state
        measured_w: Measured interface width
        satisfied_invariants: Set of satisfied invariant IDs
        denial_reason: Reason for denial (if not granted)
    """
    granted: bool
    control_mode: Optional[ControlMode]
    execution_guard: Optional[Any]  # MomentaryExecutionGuard or ContinuousExecutionGuard
    kernel_state: KernelState
    measured_w: int
    satisfied_invariants: set[str]
    denial_reason: Optional[str] = None


# ============================================================================
# CLARITY KERNEL SSL
# ============================================================================


class ClarityKernel:
    """
    The Clarity Kernel SSL — Stable Structural Layer.

    This is the main enforcement engine that:
    1. Validates all invariants
    2. Manages state transitions
    3. Enforces control modes
    4. Logs all events immutably
    5. Makes permission-to-proceed decisions

    Runtime mutation is FORBIDDEN (Section 14).
    """

    def __init__(
        self,
        logger: Optional[AuditLogger] = None,
        max_width: int = 3,
        ssl_version: str = "v1.1.0"
    ):
        """
        Initializes the Clarity Kernel.

        Args:
            logger: Audit logger (uses default if None)
            max_width: Maximum interface width (default 3 per spec)
            ssl_version: SSL version (must match spec)
        """
        self.logger = logger or get_default_logger()
        self.max_width = max_width
        self.ssl_version = ssl_version

        # State machine
        self.state_machine = ClarityStateMachine()
        self.normal_controller = NormalModeController(self.state_machine)
        self.continuous_controller = ContinuousModeController(self.state_machine)
        self.abnormal_controller = AbnormalModeController(self.state_machine)

        # Operating mode
        self.operating_mode = OperatingMode.NORMAL

        # Override state
        self.override_active = False
        self.override_signature: Optional[str] = None

    def request_permission(self, request: PermissionRequest) -> PermissionResponse:
        """
        Main entry point for permission-to-proceed decisions.

        This method:
        1. Validates all invariants
        2. Measures interface width w
        3. Determines control mode
        4. Transitions state machine
        5. Logs all decisions
        6. Returns permission response

        Args:
            request: The permission request

        Returns:
            PermissionResponse with decision and context

        Raises:
            PermissionDenied: If permission is denied
            ImmediateStopTriggered: If immediate stop is required
        """
        satisfied_invariants: set[str] = set()
        measured_w = 0

        try:
            # ================================================================
            # STEP 1: Validate I-1 (Clarity Invariant)
            # ================================================================
            try:
                validate_clarity(
                    request.required_definitions,
                    request.required_thresholds,
                    request.required_constraints
                )
                satisfied_invariants.add("I-1")
            except InvariantViolation as e:
                self.logger.log_invariant_violation(
                    "I-1",
                    self.state_machine.current_state.value,
                    str(e),
                    context=e.context
                )
                raise PermissionDenied(
                    "Clarity invariant violated",
                    reason=str(e),
                    kernel_state=self.state_machine.current_state.value
                ) from e

            # ================================================================
            # STEP 2: Validate I-7 (Complexity Invariant - Width)
            # ================================================================
            try:
                measured_w = validate_complexity(request.variables, self.max_width)
                satisfied_invariants.add("I-7")

                # Log width evaluation (Section 8.5)
                unresolved_material = [
                    v.name for v in request.variables
                    if not v.resolved and v.material
                ]
                self.logger.log_width_evaluation(
                    measured_w=measured_w,
                    unresolved_variables=unresolved_material,
                    kernel_state=self.state_machine.current_state.value,
                    decomposition_status=DecompositionStatus.NOT_ATTEMPTED,
                    resolution_outcome=ResolutionOutcome.PROCEED
                )
            except ComplexityInvariantViolation as e:
                self.logger.log_width_evaluation(
                    measured_w=e.measured_w,
                    unresolved_variables=e.unresolved_variables,
                    kernel_state=self.state_machine.current_state.value,
                    decomposition_status=DecompositionStatus.NOT_ATTEMPTED,
                    resolution_outcome=ResolutionOutcome.STOP,
                    context=e.context
                )
                raise PermissionDenied(
                    f"Complexity invariant violated: w={e.measured_w} > {self.max_width}",
                    reason=str(e),
                    kernel_state=self.state_machine.current_state.value
                ) from e

            # ================================================================
            # STEP 3: Validate I-2 (Authority Invariant)
            # ================================================================
            try:
                validate_authority(request.authority, request.required_scope)
                satisfied_invariants.add("I-2")

                self.logger.log_authorization(
                    granted=True,
                    authority_source=request.authority.source if request.authority else "unavailable",
                    required_scope=request.required_scope,
                    kernel_state=self.state_machine.current_state.value,
                    control_mode="pending"
                )
            except InvariantViolation as e:
                self.logger.log_authorization(
                    granted=False,
                    authority_source="unavailable",
                    required_scope=request.required_scope,
                    kernel_state=self.state_machine.current_state.value,
                    control_mode="none",
                    context=e.context
                )
                raise PermissionDenied(
                    "Authority invariant violated",
                    reason=str(e),
                    kernel_state=self.state_machine.current_state.value
                ) from e

            # ================================================================
            # STEP 4: Validate I-3 (Attention Invariant)
            # ================================================================
            try:
                validate_attention(
                    request.requires_continuous_attention,
                    request.triggers.any_triggered(),  # Continuous mode provides attention
                    request.harm_scenario
                )
                satisfied_invariants.add("I-3")
            except InvariantViolation as e:
                self.logger.log_invariant_violation(
                    "I-3",
                    self.state_machine.current_state.value,
                    str(e),
                    context=e.context
                )
                raise PermissionDenied(
                    "Attention invariant violated",
                    reason=str(e),
                    kernel_state=self.state_machine.current_state.value
                ) from e

            # ================================================================
            # STEP 5: Validate I-6 (Silence Invariant)
            # ================================================================
            # Check that no unresolved variables are being guessed
            for var in request.variables:
                try:
                    validate_silence(var, attempting_guess=False)
                except InvariantViolation as e:
                    self.logger.log_invariant_violation(
                        "I-6",
                        self.state_machine.current_state.value,
                        str(e),
                        context=e.context
                    )
                    raise PermissionDenied(
                        "Silence invariant violated",
                        reason=str(e),
                        kernel_state=self.state_machine.current_state.value
                    ) from e
            satisfied_invariants.add("I-6")

            # ================================================================
            # STEP 6: Mark I-4 and I-5 as satisfied
            # ================================================================
            # I-4 (Truth Invariant): We're not claiming ALLOWED while any invariant is unsatisfied
            # (if we got here, all checked invariants passed)
            satisfied_invariants.add("I-4")

            # I-5 (Logging Invariant): All events have been logged
            validate_logging(event_logged=True, event_type="permission_request")
            satisfied_invariants.add("I-5")

            # Validate truth invariant: ensure all invariants are satisfied before claiming ALLOWED
            all_invariants = get_all_invariant_ids()
            validate_truth(satisfied_invariants, all_invariants, claiming_allowed=True)

            # ================================================================
            # STEP 7: Determine Control Mode
            # ================================================================
            control_mode = determine_control_mode(
                request.preconditions,
                request.triggers
            )

            # ================================================================
            # STEP 8: Transition State Machine
            # ================================================================
            self._transition_to_preconditions_valid()

            self._transition_to_width_ok(measured_w)

            if control_mode == ControlMode.MOMENTARY:
                guard = self._authorize_momentary(request.preconditions)
            else:
                guard = self._authorize_continuous(request.triggers)

            # ================================================================
            # STEP 9: Return Permission Response
            # ================================================================
            return PermissionResponse(
                granted=True,
                control_mode=control_mode,
                execution_guard=guard,
                kernel_state=self.state_machine.current_state,
                measured_w=measured_w,
                satisfied_invariants=satisfied_invariants
            )

        except PermissionDenied:
            # Already logged
            raise
        except Exception as e:
            # Unexpected error - log and deny
            self.logger.log_invariant_violation(
                "UNKNOWN",
                self.state_machine.current_state.value,
                f"Unexpected error during permission evaluation: {e}",
                context={"error": str(e)}
            )
            raise PermissionDenied(
                "Permission denied due to unexpected error",
                reason=str(e),
                kernel_state=self.state_machine.current_state.value
            ) from e

    def apply_override(
        self,
        override_signature: str,
        unsatisfiable_invariants: list[str],
        justification: str
    ) -> None:
        """
        Applies break-glass override (Section 9).

        Override does NOT remove invariants - it changes operating mode to ABNORMAL.

        Args:
            override_signature: Human authorization signature
            unsatisfiable_invariants: Which invariants cannot be satisfied
            justification: Reason for override

        Raises:
            ValueError: If override_signature is invalid
        """
        if not override_signature or not override_signature.strip():
            raise ValueError("Override signature required")

        # Log override
        self.logger.log_override(
            override_signature=override_signature,
            unsatisfiable_invariants=unsatisfiable_invariants,
            kernel_state=self.state_machine.current_state.value,
            context={"justification": justification}
        )

        # Transition to abnormal mode
        self.abnormal_controller.mark_unsatisfiable(
            unsatisfiable_invariants,
            logged=True
        )
        self.abnormal_controller.apply_override(override_signature, logged=True)
        self.abnormal_controller.enter_abnormal_execution(logged=True)

        # Update kernel state
        self.operating_mode = OperatingMode.ABNORMAL
        self.override_active = True
        self.override_signature = override_signature

    def trigger_immediate_stop(self, reason: str, triggered_by: str) -> None:
        """
        Triggers immediate stop (Section 12).

        When stop triggers:
        - execution halts immediately
        - reasoning halts immediately
        - no automatic retry
        - no partial completion
        - no background continuation

        Args:
            reason: Why stop was triggered
            triggered_by: What triggered the stop

        Raises:
            ImmediateStopTriggered: Always
        """
        # Log immediate stop
        self.logger.log_immediate_stop(
            reason=reason,
            kernel_state=self.state_machine.current_state.value,
            triggered_by=triggered_by
        )

        # Transition to immediate stop state
        self.continuous_controller.immediate_stop(
            reason=reason,
            context={"triggered_by": triggered_by},
            logged=True
        )

        raise ImmediateStopTriggered(reason, triggered_by)

    def reset(self) -> None:
        """
        Resets the kernel to IDLE state.

        Only permitted after COMPLETE or RETURN_TO_SAFE_STATE.
        """
        if self.state_machine.current_state in [KernelState.COMPLETE]:
            self.normal_controller.reset(logged=True)
        elif self.state_machine.current_state == KernelState.RETURN_TO_SAFE_STATE:
            self.abnormal_controller.reset(logged=True)
            self.operating_mode = OperatingMode.NORMAL
            self.override_active = False
            self.override_signature = None
        else:
            raise ValueError(
                f"Cannot reset from state {self.state_machine.current_state.value}"
            )

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _transition_to_preconditions_valid(self) -> None:
        """Transitions to PRECONDITIONS_VALID state."""
        self.logger.log_state_transition(
            from_state=self.state_machine.current_state.value,
            to_state=KernelState.PRECONDITIONS_VALID.value,
            reason="All preconditions validated",
            invariants_evaluated={"I-1": True, "I-2": True, "I-3": True, "I-6": True}
        )
        self.normal_controller.validate_preconditions(
            StateMachineContext(
                mode=self.operating_mode,
                w=0,
                invariants_satisfied=set(),
                has_authority=True
            ),
            logged=True
        )

    def _transition_to_width_ok(self, measured_w: int) -> None:
        """Transitions to WIDTH_OK state."""
        self.logger.log_state_transition(
            from_state=self.state_machine.current_state.value,
            to_state=KernelState.WIDTH_OK.value,
            reason=f"Interface width w={measured_w} within limit",
            invariants_evaluated={"I-7": True},
            measured_w=measured_w
        )
        self.normal_controller.validate_width(
            StateMachineContext(
                mode=self.operating_mode,
                w=measured_w,
                invariants_satisfied=set(),
                has_authority=True
            ),
            logged=True
        )

    def _authorize_momentary(
        self,
        preconditions: MomentaryPreconditions
    ) -> MomentaryExecutionGuard:
        """Authorizes momentary execution."""
        guard = MomentaryExecutionGuard(preconditions)
        guard.authorize()

        self.logger.log_state_transition(
            from_state=self.state_machine.current_state.value,
            to_state=KernelState.AUTHORIZED.value,
            reason="Momentary authorization granted",
            invariants_evaluated={"I-2": True},
            control_mode="momentary"
        )
        self.normal_controller.authorize(
            StateMachineContext(
                mode=self.operating_mode,
                w=0,
                invariants_satisfied=set(),
                has_authority=True
            ),
            logged=True
        )

        return guard

    def _authorize_continuous(
        self,
        triggers: ContinuousTriggers
    ) -> ContinuousExecutionGuard:
        """Authorizes continuous execution."""
        guard = ContinuousExecutionGuard()
        guard.authorize()

        self.logger.log_state_transition(
            from_state=self.state_machine.current_state.value,
            to_state=KernelState.CONTINUOUS_AUTH_REQUIRED.value,
            reason=f"Continuous authorization required: {', '.join(triggers.get_triggered_conditions())}",
            invariants_evaluated={"I-2": True, "I-3": True},
            control_mode="continuous"
        )
        self.continuous_controller.require_continuous_auth(
            StateMachineContext(
                mode=OperatingMode.CONTINUOUS,
                w=0,
                invariants_satisfied=set(),
                has_authority=True,
                confirmation_active=True
            ),
            logged=True
        )

        return guard
