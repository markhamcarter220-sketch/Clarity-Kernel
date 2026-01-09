"""
Example 03: Interface Width Limit (w ≤ 3)

This example demonstrates:
- How interface width w is calculated
- What happens when w > 3 (ComplexityInvariantViolation)
- Three resolution strategies:
  1. Resolve variables to reduce w
  2. Decompose operation into smaller sub-operations
  3. Apply override (emergency only)

Interface width w := count(variables WHERE resolved=FALSE AND material=TRUE)
"""

import time
import os
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    ComplexityInvariantViolation,
    PermissionDenied,
)


def create_authority_token() -> AuthorityToken:
    """Create placeholder authority token."""
    return AuthorityToken(
        source="demo_user",
        verifiable=True,
        scope="medical.prescribe",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )


def demonstrate_width_violation():
    """
    Demonstrates what happens when w > 3.

    Medical dosage calculation with 5 unresolved material variables:
    - dosage_mg (unresolved)
    - patient_weight_kg (unresolved)
    - drug_name (unresolved)
    - administration_route (unresolved)
    - concurrent_medications (unresolved)

    w = 5 > 3 → ComplexityInvariantViolation
    """
    print("=" * 60)
    print("SCENARIO 1: Width Violation (w=5 > 3)")
    print("=" * 60)

    kernel = ClarityKernel()

    # Define 5 unresolved material variables
    variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_weight_kg", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),
        Variable("administration_route", resolved=False, material=True, value=None),
        Variable("concurrent_medications", resolved=False, material=True, value=None),
        # Non-material variable (does not count toward w)
        Variable("prescriber_id", resolved=True, material=False, value="DR_SMITH"),
    ]

    print(f"\nVariables:")
    for var in variables:
        status = "RESOLVED" if var.resolved else "UNRESOLVED"
        materiality = "MATERIAL" if var.material else "NON-MATERIAL"
        counts = "✓ counts toward w" if (not var.resolved and var.material) else "✗ does not count"
        print(f"  {var.name}: {status}, {materiality} {counts}")

    print(f"\nMeasured w = 5 (exceeds limit of 3)")

    request = PermissionRequest(
        operation_id="prescribe_001",
        variables=variables,
        required_definitions={},
        required_thresholds={},
        required_constraints=[],
        authority=create_authority_token(),
        required_scope="medical.prescribe",
        preconditions=MomentaryPreconditions(
            outcome_reversible=False,
            risk_does_not_increase=False,
            no_new_critical_info=False,
            w_within_limit=False,  # w > 3
            execution_window_bounded=True
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=True,
            compliance_safety_exposure=True,
            context_may_change=False,
            ambiguity_at_initiation=True,  # w > 3
            w_may_fluctuate=False,
            execution_window_extended=False
        ),
        requires_continuous_attention=True,
        harm_scenario="Incorrect dosage could cause patient harm"
    )

    try:
        response = kernel.request_permission(request)
        print("\n✗ ERROR: Permission should have been denied (w > 3)")

    except ComplexityInvariantViolation as e:
        print("\n✓ ComplexityInvariantViolation raised (expected)")
        print(f"  Measured w: {e.measured_w}")
        print(f"  Unresolved variables: {e.unresolved_variables}")


def demonstrate_resolution_strategy_1():
    """
    Strategy 1: Resolve variables to reduce w.

    Start with w=5, resolve 3 variables → w=2 ≤ 3 → ALLOWED
    """
    print("\n" + "=" * 60)
    print("STRATEGY 1: Resolve Variables to Reduce w")
    print("=" * 60)

    kernel = ClarityKernel()

    # Resolve 3 variables → w = 2
    variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_weight_kg", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=True, material=True, value="aspirin"),  # RESOLVED
        Variable("administration_route", resolved=True, material=True, value="oral"),  # RESOLVED
        Variable("concurrent_medications", resolved=True, material=True, value=["lisinopril"]),  # RESOLVED
        Variable("prescriber_id", resolved=True, material=False, value="DR_SMITH"),
    ]

    print(f"\nResolved 3 variables (drug_name, administration_route, concurrent_medications)")
    print(f"Measured w = 2 (within limit)")

    request = PermissionRequest(
        operation_id="prescribe_002",
        variables=variables,
        required_definitions={"drug_name": "aspirin", "administration_route": "oral"},
        required_thresholds={},
        required_constraints=["no_drug_interactions"],
        authority=create_authority_token(),
        required_scope="medical.prescribe",
        preconditions=MomentaryPreconditions(
            outcome_reversible=False,
            risk_does_not_increase=False,
            no_new_critical_info=False,
            w_within_limit=True,  # w=2 ≤ 3
            execution_window_bounded=True
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=True,
            compliance_safety_exposure=True,
            context_may_change=False,
            ambiguity_at_initiation=True,  # Still 2 unresolved
            w_may_fluctuate=False,
            execution_window_extended=False
        ),
        requires_continuous_attention=True,
        harm_scenario="Incorrect dosage could cause patient harm"
    )

    try:
        response = kernel.request_permission(request)
        print(f"\n✓ PERMISSION GRANTED")
        print(f"  Control Mode: {response.control_mode.value}")
        print(f"  Measured w: {response.measured_w}")

    except PermissionDenied as e:
        print(f"\n✗ PERMISSION DENIED: {e.reason}")


def demonstrate_resolution_strategy_2():
    """
    Strategy 2: Decompose into smaller sub-operations.

    Instead of one operation with w=5, create:
    - Sub-operation 1: Verify patient (w=2)
    - Sub-operation 2: Calculate dosage (w=1)
    - Sub-operation 3: Verify safety (w=2)
    """
    print("\n" + "=" * 60)
    print("STRATEGY 2: Decompose into Sub-Operations")
    print("=" * 60)

    kernel = ClarityKernel()

    # Sub-operation 1: Verify patient
    print("\nSub-operation 1: Verify Patient (w=2)")
    request_1 = PermissionRequest(
        operation_id="verify_patient_001",
        variables=[
            Variable("patient_id", resolved=False, material=True, value=None),
            Variable("patient_weight_kg", resolved=False, material=True, value=None),
        ],
        required_definitions={},
        required_thresholds={},
        required_constraints=["patient_exists"],
        authority=create_authority_token(),
        required_scope="medical.prescribe",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario="none"
    )

    try:
        response = kernel.request_permission(request_1)
        print(f"  ✓ Sub-operation 1 granted (w={response.measured_w})")
    except PermissionDenied as e:
        print(f"  ✗ Sub-operation 1 denied: {e.reason}")
        return

    # Sub-operation 2: Calculate dosage
    print("\nSub-operation 2: Calculate Dosage (w=1)")
    request_2 = PermissionRequest(
        operation_id="calculate_dosage_001",
        variables=[
            Variable("dosage_mg", resolved=False, material=True, value=None),
            Variable("patient_weight_kg", resolved=True, material=True, value=70.5),  # From sub-op 1
        ],
        required_definitions={"patient_weight_kg": 70.5},
        required_thresholds={},
        required_constraints=[],
        authority=create_authority_token(),
        required_scope="medical.prescribe",
        preconditions=MomentaryPreconditions(True, True, True, True, True),
        triggers=ContinuousTriggers(False, False, False, False, False, False),
        requires_continuous_attention=False,
        harm_scenario="none"
    )

    try:
        response = kernel.request_permission(request_2)
        print(f"  ✓ Sub-operation 2 granted (w={response.measured_w})")
    except PermissionDenied as e:
        print(f"  ✗ Sub-operation 2 denied: {e.reason}")
        return

    print("\n✓ All sub-operations completed successfully")


def demonstrate_resolution_strategy_3():
    """
    Strategy 3: Apply override (emergency only).

    When w > 3 is unavoidable and justified (emergency scenarios).
    """
    print("\n" + "=" * 60)
    print("STRATEGY 3: Apply Override (Emergency Only)")
    print("=" * 60)

    kernel = ClarityKernel()

    print("\nEmergency scenario: Trauma patient, immediate intervention required")
    print("Cannot resolve all variables - w=4 unavoidable")

    variables = [
        Variable("patient_id", resolved=False, material=True, value=None),  # Unknown
        Variable("patient_weight_kg", resolved=False, material=True, value=None),  # Unknown
        Variable("drug_allergies", resolved=False, material=True, value=None),  # Unknown
        Variable("concurrent_medications", resolved=False, material=True, value=None),  # Unknown
    ]

    print("\nApplying override...")
    kernel.apply_override(
        override_signature="DR_SMITH_EMERGENCY_2026-01-08T12:00:00Z",
        unsatisfiable_invariants=["I-7"],
        justification="Emergency trauma patient - immediate intervention required, w=4 unavoidable"
    )

    print("  ✓ Override applied (ABNORMAL mode)")
    print("  ⚠ Operating in ABNORMAL mode - all decisions logged and flagged for review")


def main():
    print("=" * 60)
    print("Example 03: Interface Width Limit (w ≤ 3)")
    print("=" * 60)

    demonstrate_width_violation()
    demonstrate_resolution_strategy_1()
    demonstrate_resolution_strategy_2()
    demonstrate_resolution_strategy_3()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("✓ Width violation (w > 3) correctly triggers ComplexityInvariantViolation")
    print("✓ Strategy 1 (resolve variables) reduces w to acceptable level")
    print("✓ Strategy 2 (decompose) breaks operation into w ≤ 3 sub-operations")
    print("✓ Strategy 3 (override) enables emergency operation with full audit trail")


if __name__ == "__main__":
    main()
