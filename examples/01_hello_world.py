"""
Example 01: Hello World - Simplest Possible Request

This example demonstrates the absolute minimum required to use the Clarity Kernel:
- Create a kernel instance
- Build a permission request with all required fields
- Handle the response

This is a read-only operation with no unresolved variables (w=0).
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
    PermissionDenied,
)


def main():
    print("=" * 60)
    print("Example 01: Hello World - Simplest Possible Request")
    print("=" * 60)

    # Step 1: Create kernel instance
    kernel = ClarityKernel()
    print("\n✓ Kernel initialized")

    # Step 2: Create authority token
    # NOTE: This is a placeholder token for demonstration.
    # In production, use cryptographically signed tokens (see example 02).
    authority = AuthorityToken(
        source="demo_user",
        verifiable=True,
        scope="demo.read",
        signature=b'\x00' * 64,  # Placeholder - use real Ed25519 signature in production
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32  # Placeholder - use real public key in production
    )
    print("✓ Authority token created (placeholder for demo)")

    # Step 3: Define variables
    # All variables are resolved - no unresolved material variables (w=0)
    variables = [
        Variable(
            name="message",
            resolved=True,
            material=True,
            value="Hello, Clarity Kernel!"
        )
    ]
    print("✓ Variables defined (w=0)")

    # Step 4: Build permission request
    request = PermissionRequest(
        operation_id="hello_world_001",
        variables=variables,
        required_definitions={"message": "Hello, Clarity Kernel!"},
        required_thresholds={},
        required_constraints=["message_defined"],
        authority=authority,
        required_scope="demo.read",
        preconditions=MomentaryPreconditions(
            outcome_reversible=True,      # Read operation is reversible
            risk_does_not_increase=True,  # No risk
            no_new_critical_info=True,    # No new info expected
            w_within_limit=True,          # w=0 ≤ 3
            execution_window_bounded=True # Instant operation
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=False,        # Can be undone
            compliance_safety_exposure=False,  # No compliance concern
            context_may_change=False,          # Context stable
            ambiguity_at_initiation=False,     # No ambiguity
            w_may_fluctuate=False,             # w is stable
            execution_window_extended=False    # Quick operation
        ),
        requires_continuous_attention=False,
        harm_scenario="none"
    )
    print("✓ Permission request built")

    # Step 5: Request permission
    try:
        response = kernel.request_permission(request)

        print("\n" + "=" * 60)
        print("PERMISSION GRANTED")
        print("=" * 60)
        print(f"Control Mode: {response.control_mode.value}")
        print(f"Interface Width (w): {response.measured_w}")
        print(f"Satisfied Invariants: {sorted(response.satisfied_invariants)}")
        print(f"Kernel State: {response.kernel_state.value}")

        # Step 6: Execute operation (since permission granted)
        message = variables[0].value
        print("\n" + "=" * 60)
        print(f"EXECUTING: {message}")
        print("=" * 60)

    except PermissionDenied as e:
        print("\n" + "=" * 60)
        print("PERMISSION DENIED")
        print("=" * 60)
        print(f"Reason: {e.reason}")
        print(f"Kernel State: {e.kernel_state}")


if __name__ == "__main__":
    main()
