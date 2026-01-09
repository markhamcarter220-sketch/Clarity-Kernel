"""
Example 05: Continuous Authorization (Long-Running Operations)

This example demonstrates:
- When continuous authorization is required vs momentary
- How to implement deadman switch / confirmation mechanism
- What happens when authorization is lost mid-execution
- Immediate stop semantics

Continuous authorization is required when ANY of these triggers are true:
- outcome_irreversible: The outcome is permanent
- compliance_safety_exposure: Compliance or safety concerns exist
- context_may_change: Context can change during execution
- ambiguity_at_initiation: Ambiguity exists at start
- w_may_fluctuate: Interface width w may change during execution
- execution_window_extended: Execution time is long (≥ 1 minute)
"""

import time
import os
import threading
from datetime import datetime, timedelta
from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    ControlMode,
    PermissionDenied,
    ImmediateStopTriggered,
)


def create_authority_token() -> AuthorityToken:
    """Create placeholder authority token."""
    return AuthorityToken(
        source="demo_user",
        verifiable=True,
        scope="financial.transfer",
        signature=b'\x00' * 64,
        timestamp=int(time.time()),
        nonce=os.urandom(32),
        issuer_pubkey=b'\x00' * 32
    )


class ConfirmationMechanism:
    """
    Simulates a deadman switch / continuous confirmation mechanism.

    In production, this could be:
    - Physical button/switch
    - Periodic user confirmation prompts
    - Biometric presence detection
    - Network heartbeat from supervisor
    """

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds
        self.last_confirmation = datetime.now()
        self.running = True
        self.lock = threading.Lock()

    def confirm(self) -> None:
        """Update last confirmation timestamp."""
        with self.lock:
            self.last_confirmation = datetime.now()
            print(f"  ✓ Confirmation received at {self.last_confirmation.strftime('%H:%M:%S')}")

    def check_confirmation(self) -> bool:
        """Check if confirmation is still valid (within timeout)."""
        with self.lock:
            elapsed = (datetime.now() - self.last_confirmation).total_seconds()
            is_valid = elapsed < self.timeout_seconds

            if not is_valid:
                print(f"  ✗ Confirmation lost (last confirmed {elapsed:.1f}s ago)")
            return is_valid

    def start_periodic_check(self, interval_seconds: int = 2):
        """Start background thread to check confirmation periodically."""
        def check_loop():
            while self.running:
                time.sleep(interval_seconds)
                if self.running:
                    self.check_confirmation()

        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()


def demonstrate_continuous_vs_momentary():
    """
    Compares momentary vs continuous authorization requirements.
    """
    print("=" * 60)
    print("CONTINUOUS VS MOMENTARY AUTHORIZATION")
    print("=" * 60)

    # Momentary: Simple file read
    print("\nExample A: File Read (MOMENTARY)")
    print("-" * 60)
    print("Preconditions:")
    print("  ✓ outcome_reversible: True (can be re-read)")
    print("  ✓ risk_does_not_increase: True (no risk)")
    print("  ✓ no_new_critical_info: True (file stable)")
    print("  ✓ w_within_limit: True (w=0)")
    print("  ✓ execution_window_bounded: True (instant)")
    print("\nTriggers:")
    print("  ✗ outcome_irreversible: False")
    print("  ✗ compliance_safety_exposure: False")
    print("  ✗ context_may_change: False")
    print("  ✗ ambiguity_at_initiation: False")
    print("  ✗ w_may_fluctuate: False")
    print("  ✗ execution_window_extended: False")
    print("\nResult: MOMENTARY authorization sufficient")

    # Continuous: Financial transfer
    print("\n\nExample B: Financial Transfer (CONTINUOUS)")
    print("-" * 60)
    print("Preconditions:")
    print("  ✗ outcome_reversible: False (permanent transfer)")
    print("  ✗ risk_does_not_increase: False (fraud risk)")
    print("  ✗ no_new_critical_info: False (fraud alerts may emerge)")
    print("  ✓ w_within_limit: True (w=0)")
    print("  ✓ execution_window_bounded: True (quick transfer)")
    print("\nTriggers:")
    print("  ✓ outcome_irreversible: True → REQUIRES CONTINUOUS")
    print("  ✓ compliance_safety_exposure: True → REQUIRES CONTINUOUS")
    print("  ✓ context_may_change: True → REQUIRES CONTINUOUS")
    print("  ✗ ambiguity_at_initiation: False")
    print("  ✗ w_may_fluctuate: False")
    print("  ✗ execution_window_extended: False")
    print("\nResult: CONTINUOUS authorization required (3 triggers)")


def demonstrate_continuous_operation_success():
    """
    Demonstrates successful long-running operation with continuous auth.
    """
    print("\n" + "=" * 60)
    print("CONTINUOUS OPERATION: SUCCESS CASE")
    print("=" * 60)

    kernel = ClarityKernel()

    # Define operation: Multi-step financial transfer
    print("\nOperation: Large financial transfer (10 steps)")
    print("Each step takes 2 seconds")
    print("Total execution time: 20 seconds")

    request = PermissionRequest(
        operation_id="transfer_large_001",
        variables=[
            Variable("amount", resolved=True, material=True, value=100000),
            Variable("recipient", resolved=True, material=True, value="ACCT_98765"),
        ],
        required_definitions={"amount": 100000, "recipient": "ACCT_98765"},
        required_thresholds={"max_transfer": 100000},
        required_constraints=["sufficient_funds", "recipient_verified"],
        authority=create_authority_token(),
        required_scope="financial.transfer",
        preconditions=MomentaryPreconditions(
            outcome_reversible=False,
            risk_does_not_increase=False,
            no_new_critical_info=False,
            w_within_limit=True,
            execution_window_bounded=False  # Long operation
        ),
        triggers=ContinuousTriggers(
            outcome_irreversible=True,          # TRIGGER
            compliance_safety_exposure=True,    # TRIGGER
            context_may_change=True,            # TRIGGER
            ambiguity_at_initiation=False,
            w_may_fluctuate=False,
            execution_window_extended=True      # TRIGGER
        ),
        requires_continuous_attention=True,
        harm_scenario="Large financial transfer cannot be reversed if fraud detected mid-execution"
    )

    try:
        response = kernel.request_permission(request)

        print(f"\n✓ Permission granted: {response.control_mode.value}")

        if response.control_mode == ControlMode.CONTINUOUS:
            print("\nContinuous authorization required")
            print("Setting up confirmation mechanism...")

            # Create confirmation mechanism with 10-second timeout
            confirm_mechanism = ConfirmationMechanism(timeout_seconds=10)

            print("\nExecuting operation with continuous confirmation...")
            print("(Simulating user confirming every 5 seconds)\n")

            # Simulate 10-step operation
            for step in range(1, 11):
                print(f"Step {step}/10: Processing...")
                time.sleep(2)  # Simulate work

                # Check confirmation
                if not confirm_mechanism.check_confirmation():
                    kernel.trigger_immediate_stop(
                        reason="Continuous authorization lost",
                        triggered_by="confirmation_mechanism"
                    )

                # Simulate user confirmation every 5 seconds
                if step % 3 == 0:  # After steps 3, 6, 9
                    confirm_mechanism.confirm()

            print("\n✓ Operation completed successfully")
            print("✓ Continuous authorization maintained throughout")

    except PermissionDenied as e:
        print(f"\n✗ Permission denied: {e.reason}")

    except ImmediateStopTriggered as e:
        print(f"\n✗ IMMEDIATE STOP: {e.trigger}")
        print("  → Operation halted")
        print("  → No partial completion")
        print("  → Requires manual review")


def demonstrate_continuous_operation_lost_auth():
    """
    Demonstrates what happens when authorization is lost mid-execution.
    """
    print("\n" + "=" * 60)
    print("CONTINUOUS OPERATION: AUTHORIZATION LOST")
    print("=" * 60)

    kernel = ClarityKernel()

    print("\nOperation: Large financial transfer (10 steps)")
    print("Authorization will be lost at step 5")

    request = PermissionRequest(
        operation_id="transfer_large_002",
        variables=[
            Variable("amount", resolved=True, material=True, value=100000),
            Variable("recipient", resolved=True, material=True, value="ACCT_98765"),
        ],
        required_definitions={"amount": 100000, "recipient": "ACCT_98765"},
        required_thresholds={"max_transfer": 100000},
        required_constraints=["sufficient_funds"],
        authority=create_authority_token(),
        required_scope="financial.transfer",
        preconditions=MomentaryPreconditions(False, False, False, True, False),
        triggers=ContinuousTriggers(True, True, True, False, False, True),
        requires_continuous_attention=True,
        harm_scenario="Large financial transfer cannot be reversed"
    )

    try:
        response = kernel.request_permission(request)

        if response.control_mode == ControlMode.CONTINUOUS:
            print(f"\n✓ Permission granted: {response.control_mode.value}")

            # Create confirmation mechanism
            confirm_mechanism = ConfirmationMechanism(timeout_seconds=5)
            confirm_mechanism.confirm()  # Initial confirmation

            print("\nExecuting operation...")
            print("(Authorization will be lost - no confirmation after step 2)\n")

            # Simulate 10-step operation
            for step in range(1, 11):
                print(f"Step {step}/10: Processing...")

                # Simulate authorization loss at step 5
                if step >= 5:
                    if not confirm_mechanism.check_confirmation():
                        # Authorization lost - trigger immediate stop
                        kernel.trigger_immediate_stop(
                            reason="Continuous authorization confirmation lost",
                            triggered_by="confirmation_timeout"
                        )

                time.sleep(1)

                # Only confirm for first 2 steps
                if step <= 2:
                    confirm_mechanism.confirm()

    except ImmediateStopTriggered as e:
        print(f"\n✓ IMMEDIATE STOP TRIGGERED (expected)")
        print(f"  Trigger: {e.trigger}")
        print(f"  Reason: {str(e)}")
        print("\nStop semantics:")
        print("  ✓ Execution halted immediately")
        print("  ✓ No automatic retry")
        print("  ✓ No partial completion")
        print("  ✓ No background continuation")
        print("  ✓ All context logged for manual review")


def demonstrate_implementation_patterns():
    """
    Shows common implementation patterns for continuous authorization.
    """
    print("\n" + "=" * 60)
    print("IMPLEMENTATION PATTERNS")
    print("=" * 60)

    print("\nPattern 1: Physical Deadman Switch")
    print("-" * 60)
    print("Hardware button that must be held during operation")
    print("If released → immediate stop")
    print("\nUse cases:")
    print("  - Autonomous vehicle operation")
    print("  - Industrial machinery control")
    print("  - Medical device operation")

    print("\n\nPattern 2: Periodic User Confirmation")
    print("-" * 60)
    print("Prompt user every N seconds to confirm continuation")
    print("If no response within timeout → immediate stop")
    print("\nUse cases:")
    print("  - Long-running financial operations")
    print("  - Batch data processing with privacy concerns")
    print("  - Multi-step compliance workflows")

    print("\n\nPattern 3: Biometric Presence Detection")
    print("-" * 60)
    print("Continuous monitoring of operator presence (face/fingerprint)")
    print("If presence lost → immediate stop")
    print("\nUse cases:")
    print("  - High-security operations")
    print("  - Remote system administration")
    print("  - Critical infrastructure control")

    print("\n\nPattern 4: Network Heartbeat")
    print("-" * 60)
    print("Supervisor system sends periodic heartbeat")
    print("If heartbeat lost → immediate stop")
    print("\nUse cases:")
    print("  - Distributed system coordination")
    print("  - Multi-agent operations")
    print("  - Failsafe for network partition")


def main():
    print("=" * 60)
    print("Example 05: Continuous Authorization")
    print("=" * 60)

    demonstrate_continuous_vs_momentary()
    demonstrate_continuous_operation_success()
    demonstrate_continuous_operation_lost_auth()
    demonstrate_implementation_patterns()

    print("\n" + "=" * 60)
    print("KEY INSIGHTS")
    print("=" * 60)
    print("\n1. Continuous authorization ≠ re-authorization")
    print("   Not requesting permission again - confirming ongoing validity")

    print("\n2. Immediate stop is final")
    print("   No partial completion, no automatic retry, no recovery")

    print("\n3. Confirmation mechanism is application-specific")
    print("   Kernel enforces the requirement, application implements mechanism")

    print("\n4. Context changes require continuous mode")
    print("   If fraud alert, sensor anomaly, or critical info emerges → must stop")

    print("\n5. Timeout is safety-critical")
    print("   Too long → risk window expands")
    print("   Too short → false positives")
    print("   Typical: 5-30 seconds depending on risk")


if __name__ == "__main__":
    main()
