"""
Clarity Kernel Hard Invariants (Section 5)

This module implements the seven non-negotiable hard invariants that govern
the Clarity Kernel's permission-to-proceed decisions.

All invariant violations MUST raise exceptions. No warnings. No soft failures.
"""

from dataclasses import dataclass
from typing import Any, Optional, Set
from enum import Enum


# ============================================================================
# EXCEPTION TYPES (one per invariant)
# ============================================================================


class InvariantViolation(Exception):
    """Base class for all invariant violations."""

    def __init__(self, message: str, invariant_id: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.invariant_id = invariant_id
        self.context = context or {}


class ClarityInvariantViolation(InvariantViolation):
    """
    I-1: Clarity Invariant

    If required definitions, thresholds, constraints, or conditions are ambiguous → STOP
    """

    def __init__(self, message: str, ambiguous_elements: list[str], context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-1", context)
        self.ambiguous_elements = ambiguous_elements


class AuthorityInvariantViolation(InvariantViolation):
    """
    I-2: Authority Invariant

    If authority to proceed is not explicit and verifiable → STOP
    """

    def __init__(self, message: str, required_authority: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-2", context)
        self.required_authority = required_authority


class AttentionInvariantViolation(InvariantViolation):
    """
    I-3: Attention Invariant

    If continuation without sustained human attention could cause harm → CONTINUOUS AUTHORIZATION REQUIRED
    """

    def __init__(self, message: str, harm_scenario: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-3", context)
        self.harm_scenario = harm_scenario


class TruthInvariantViolation(InvariantViolation):
    """
    I-4: Truth Invariant

    The system must never indicate a "safe/approved/allowed" state while any invariant is unsatisfied.
    """

    def __init__(self, message: str, unsatisfied_invariants: list[str], context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-4", context)
        self.unsatisfied_invariants = unsatisfied_invariants


class LoggingInvariantViolation(InvariantViolation):
    """
    I-5: Logging Invariant

    Every invariant violation or bypass attempt must be:
    - logged with full context
    - flagged for review
    - never silently suppressed
    - retained as immutable record (append-only)
    """

    def __init__(self, message: str, suppression_attempt: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-5", context)
        self.suppression_attempt = suppression_attempt


class SilenceInvariantViolation(InvariantViolation):
    """
    I-6: Silence Invariant

    Guessing is forbidden. Pause/refusal/silence is valid and correct output.
    """

    def __init__(self, message: str, guessed_value: Any, variable_name: str, context: Optional[dict[str, Any]] = None):
        super().__init__(message, "I-6", context)
        self.guessed_value = guessed_value
        self.variable_name = variable_name


class ComplexityInvariantViolation(InvariantViolation):
    """
    I-7: Complexity Invariant (Bounded Interface)

    If unresolved interface width w > 3 → STOP or DECOMPOSE (never guess to reduce w).
    """

    def __init__(
        self,
        message: str,
        measured_w: int,
        unresolved_variables: list[str],
        context: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, "I-7", context)
        self.measured_w = measured_w
        self.unresolved_variables = unresolved_variables


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class Variable:
    """
    Represents a variable in the constraint system.

    Attributes:
        name: Variable identifier
        resolved: Whether the value is known
        material: Whether the variable materially affects permission decision
        value: The resolved value (None if unresolved)
    """
    name: str
    resolved: bool
    material: bool
    value: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.resolved and self.value is None:
            raise ValueError(f"Variable {self.name} marked as resolved but has no value")


@dataclass(frozen=True)
class AuthorityToken:
    """
    Represents an explicit authorization.

    Attributes:
        source: Identity/role of authorizer
        verifiable: Whether the authority can be cryptographically verified
        scope: What this authority permits
        timestamp: When authority was granted (if applicable)
    """
    source: str
    verifiable: bool
    scope: str
    timestamp: Optional[str] = None


# ============================================================================
# VALIDATORS (one per invariant)
# ============================================================================


def validate_clarity(
    required_definitions: dict[str, Any],
    required_thresholds: dict[str, Any],
    required_constraints: list[str]
) -> None:
    """
    I-1: Clarity Invariant Validator

    Checks that all required definitions, thresholds, and constraints are unambiguous.

    Args:
        required_definitions: Dictionary of required definitions
        required_thresholds: Dictionary of required thresholds
        required_constraints: List of required constraints

    Raises:
        ClarityInvariantViolation: If any element is None, empty, or ambiguous
    """
    ambiguous: list[str] = []

    # Check definitions
    for key, value in required_definitions.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            ambiguous.append(f"definition:{key}")

    # Check thresholds
    for key, value in required_thresholds.items():
        if value is None:
            ambiguous.append(f"threshold:{key}")

    # Check constraints
    for constraint in required_constraints:
        if not constraint or not constraint.strip():
            ambiguous.append(f"constraint:{constraint}")

    if ambiguous:
        raise ClarityInvariantViolation(
            f"Required elements are ambiguous or undefined: {', '.join(ambiguous)}",
            ambiguous_elements=ambiguous,
            context={
                "definitions": required_definitions,
                "thresholds": required_thresholds,
                "constraints": required_constraints
            }
        )


def validate_authority(
    authority: Optional[AuthorityToken],
    required_scope: str
) -> None:
    """
    I-2: Authority Invariant Validator

    Checks that authority to proceed is explicit and verifiable.

    Args:
        authority: The authority token (None if unavailable)
        required_scope: The scope of authority required

    Raises:
        AuthorityInvariantViolation: If authority is missing, not verifiable, or wrong scope
    """
    if authority is None:
        raise AuthorityInvariantViolation(
            f"No authority provided for scope: {required_scope}",
            required_authority=required_scope,
            context={"required_scope": required_scope}
        )

    if not authority.verifiable:
        raise AuthorityInvariantViolation(
            f"Authority from {authority.source} is not verifiable",
            required_authority=required_scope,
            context={"authority": authority, "required_scope": required_scope}
        )

    if authority.scope != required_scope:
        raise AuthorityInvariantViolation(
            f"Authority scope mismatch: have '{authority.scope}', need '{required_scope}'",
            required_authority=required_scope,
            context={"authority": authority, "required_scope": required_scope}
        )


def validate_attention(
    requires_continuous_attention: bool,
    attention_available: bool,
    harm_scenario: str
) -> None:
    """
    I-3: Attention Invariant Validator

    Checks that continuous authorization is required when harm could occur without attention.

    Args:
        requires_continuous_attention: Whether the operation requires sustained attention
        attention_available: Whether continuous attention can be provided
        harm_scenario: Description of potential harm

    Raises:
        AttentionInvariantViolation: If continuous attention required but not available
    """
    if requires_continuous_attention and not attention_available:
        raise AttentionInvariantViolation(
            f"Continuous attention required but not available: {harm_scenario}",
            harm_scenario=harm_scenario,
            context={
                "requires_continuous_attention": requires_continuous_attention,
                "attention_available": attention_available
            }
        )


def validate_truth(
    satisfied_invariants: Set[str],
    all_invariants: Set[str],
    claiming_allowed: bool
) -> None:
    """
    I-4: Truth Invariant Validator

    Ensures the system never indicates "safe/approved/allowed" while any invariant is unsatisfied.

    Args:
        satisfied_invariants: Set of invariant IDs that are satisfied
        all_invariants: Set of all invariant IDs that must be satisfied
        claiming_allowed: Whether the system is attempting to signal ALLOWED

    Raises:
        TruthInvariantViolation: If claiming allowed while invariants are unsatisfied
    """
    unsatisfied = all_invariants - satisfied_invariants

    if claiming_allowed and unsatisfied:
        raise TruthInvariantViolation(
            f"Cannot claim ALLOWED state while invariants are unsatisfied: {', '.join(sorted(unsatisfied))}",
            unsatisfied_invariants=list(unsatisfied),
            context={
                "satisfied_invariants": satisfied_invariants,
                "unsatisfied_invariants": unsatisfied
            }
        )


def validate_logging(
    event_logged: bool,
    event_type: str,
    suppression_detected: bool = False
) -> None:
    """
    I-5: Logging Invariant Validator

    Ensures all invariant violations and bypass attempts are logged immutably.

    Args:
        event_logged: Whether the event was logged
        event_type: Type of event (violation, bypass, etc.)
        suppression_detected: Whether log suppression was detected

    Raises:
        LoggingInvariantViolation: If event not logged or suppression detected
    """
    if suppression_detected:
        raise LoggingInvariantViolation(
            f"Log suppression detected for event: {event_type}",
            suppression_attempt=event_type,
            context={"event_type": event_type}
        )

    if not event_logged:
        raise LoggingInvariantViolation(
            f"Event not logged: {event_type}",
            suppression_attempt=event_type,
            context={"event_type": event_type}
        )


def validate_silence(
    variable: Variable,
    attempting_guess: bool
) -> None:
    """
    I-6: Silence Invariant Validator

    Ensures guessing is forbidden when variables are unresolved.

    Args:
        variable: The variable in question
        attempting_guess: Whether a guess is being attempted

    Raises:
        SilenceInvariantViolation: If guessing is attempted for unresolved variable
    """
    if not variable.resolved and attempting_guess:
        raise SilenceInvariantViolation(
            f"Guessing forbidden for unresolved variable: {variable.name}",
            guessed_value=variable.value,
            variable_name=variable.name,
            context={"variable": variable}
        )


def validate_complexity(
    variables: list[Variable],
    max_width: int = 3
) -> int:
    """
    I-7: Complexity Invariant Validator

    Measures unresolved interface width w and enforces w ≤ 3.

    Args:
        variables: List of all variables in the constraint system
        max_width: Maximum allowed width (default 3 per spec)

    Returns:
        The measured width w

    Raises:
        ComplexityInvariantViolation: If w > max_width
    """
    # Calculate w: number of unresolved material variables
    unresolved_material = [
        v for v in variables
        if not v.resolved and v.material
    ]

    w = len(unresolved_material)

    if w > max_width:
        unresolved_names = [v.name for v in unresolved_material]
        raise ComplexityInvariantViolation(
            f"Interface width w={w} exceeds maximum {max_width}. "
            f"Unresolved material variables: {', '.join(unresolved_names)}",
            measured_w=w,
            unresolved_variables=unresolved_names,
            context={
                "all_variables": variables,
                "max_width": max_width
            }
        )

    return w


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_all_invariant_ids() -> Set[str]:
    """Returns the set of all hard invariant IDs."""
    return {"I-1", "I-2", "I-3", "I-4", "I-5", "I-6", "I-7"}


def is_invariant_satisfied(invariant_id: str, **kwargs: Any) -> bool:
    """
    Checks if a specific invariant is satisfied without raising an exception.

    Args:
        invariant_id: The invariant to check
        **kwargs: Arguments required for the specific invariant validator

    Returns:
        True if satisfied, False otherwise
    """
    try:
        if invariant_id == "I-1":
            validate_clarity(
                kwargs.get("required_definitions", {}),
                kwargs.get("required_thresholds", {}),
                kwargs.get("required_constraints", [])
            )
        elif invariant_id == "I-2":
            validate_authority(
                kwargs.get("authority"),
                kwargs.get("required_scope", "")
            )
        elif invariant_id == "I-3":
            validate_attention(
                kwargs.get("requires_continuous_attention", False),
                kwargs.get("attention_available", False),
                kwargs.get("harm_scenario", "")
            )
        elif invariant_id == "I-4":
            validate_truth(
                kwargs.get("satisfied_invariants", set()),
                kwargs.get("all_invariants", get_all_invariant_ids()),
                kwargs.get("claiming_allowed", False)
            )
        elif invariant_id == "I-5":
            validate_logging(
                kwargs.get("event_logged", False),
                kwargs.get("event_type", ""),
                kwargs.get("suppression_detected", False)
            )
        elif invariant_id == "I-6":
            validate_silence(
                kwargs.get("variable", Variable("", False, False)),
                kwargs.get("attempting_guess", False)
            )
        elif invariant_id == "I-7":
            validate_complexity(
                kwargs.get("variables", []),
                kwargs.get("max_width", 3)
            )
        else:
            return False

        return True
    except InvariantViolation:
        return False
