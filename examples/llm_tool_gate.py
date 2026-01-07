"""
LLM Tool Call Gating Example

This example demonstrates how the Clarity Kernel gates LLM-proposed tool calls.

Key principle:
    LLMs may propose actions.
    The Clarity Kernel decides whether they happen.

The kernel evaluates:
- Clarity: Are all parameters unambiguous?
- Authority: Is there explicit permission?
- Complexity: Is w ≤ 3?
- Other invariants as defined in SPECIFICATION.md

The LLM is NOT authoritative. The kernel is.
"""

from clarity_kernel import (
    ClarityKernel,
    PermissionRequest,
    Variable,
    AuthorityToken,
    MomentaryPreconditions,
    ContinuousTriggers,
    PermissionDenied,
)


# ============================================================================
# FAKE TOOL (simulates destructive operation)
# ============================================================================

def delete_file(path: str) -> None:
    """
    Simulated file deletion tool.

    In production, this would actually delete a file.
    The Clarity Kernel prevents execution when safety conditions are not met.
    """
    print(f"[TOOL EXECUTED] Deleting file: {path}")
    print(f"[TOOL EXECUTED] File {path} has been deleted.")


# ============================================================================
# SIMULATED LLM PROPOSALS
# ============================================================================

# Proposal 1: Valid - all conditions clear
llm_proposal_valid = {
    "tool": "delete_file",
    "arguments": {
        "path": "/tmp/cache/old_log.txt"  # Clear, specific path
    },
    "context": {
        "user_intent": "delete temporary cache files",
        "authority_provided": True,
        "scope": "delete_temp_files"
    }
}

# Proposal 2: Invalid - ambiguous path (violates I-1: Clarity Invariant)
llm_proposal_ambiguous = {
    "tool": "delete_file",
    "arguments": {
        "path": None  # AMBIGUOUS - which file?
    },
    "context": {
        "user_intent": "clean up files",
        "authority_provided": True,
        "scope": "delete_files"
    }
}

# Proposal 3: Invalid - no authority (violates I-2: Authority Invariant)
llm_proposal_no_auth = {
    "tool": "delete_file",
    "arguments": {
        "path": "/important/data.csv"
    },
    "context": {
        "user_intent": "delete data file",
        "authority_provided": False,  # NO AUTHORITY
        "scope": "delete_files"
    }
}


# ============================================================================
# PERMISSION REQUEST BUILDER
# ============================================================================

def build_permission_request(llm_proposal: dict) -> PermissionRequest:
    """
    Converts an LLM tool proposal into a Clarity Kernel PermissionRequest.

    This is where we translate the LLM's suggestion into the kernel's
    formal permission-evaluation framework.

    Args:
        llm_proposal: LLM's proposed tool call

    Returns:
        PermissionRequest for kernel evaluation
    """
    tool_name = llm_proposal["tool"]
    arguments = llm_proposal["arguments"]
    context = llm_proposal["context"]

    # Convert tool arguments to Variables
    # The kernel needs to know which arguments are resolved and material
    variables = []
    for arg_name, arg_value in arguments.items():
        variables.append(
            Variable(
                name=arg_name,
                resolved=(arg_value is not None),  # Is the value known?
                material=True,  # Does it affect the permission decision?
                value=arg_value
            )
        )

    # Define required clarity elements
    # These must be unambiguous for the kernel to allow continuation
    required_definitions = {
        "tool_name": tool_name,
        "path": arguments.get("path"),  # Must be defined for clarity
    }

    # Define required thresholds (if any)
    required_thresholds = {
        "max_path_depth": 10  # Example constraint
    }

    # Define required constraints
    required_constraints = [
        "path must not be None",
        "path must be absolute or relative",
        "operation is file deletion"
    ]

    # Authority token (represents human or system authorization)
    authority = None
    if context.get("authority_provided"):
        authority = AuthorityToken(
            source="human_operator",
            verifiable=True,
            scope=context["scope"]
        )

    # Preconditions for momentary authorization
    # File deletion is reversible (from backups), low risk, bounded execution
    preconditions = MomentaryPreconditions(
        outcome_reversible=True,  # Can restore from backup
        risk_does_not_increase=True,  # One-time operation
        no_new_critical_info=True,  # No mid-execution changes expected
        w_within_limit=(len([v for v in variables if not v.resolved and v.material]) <= 3),
        execution_window_bounded=True  # Quick operation
    )

    # Continuous authorization triggers
    # For file deletion, we don't require continuous auth if conditions are met
    triggers = ContinuousTriggers(
        outcome_irreversible=False,  # Reversible via backup
        compliance_safety_exposure=False,  # Low compliance risk for temp files
        context_may_change=False,
        ambiguity_at_initiation=False,
        w_may_fluctuate=False,
        execution_window_extended=False
    )

    return PermissionRequest(
        operation_id=f"{tool_name}:{arguments.get('path', 'unknown')}",
        variables=variables,
        required_definitions=required_definitions,
        required_thresholds=required_thresholds,
        required_constraints=required_constraints,
        authority=authority,
        required_scope=context["scope"],
        preconditions=preconditions,
        triggers=triggers,
        requires_continuous_attention=False,
        harm_scenario=""  # Low harm for temp file deletion
    )


# ============================================================================
# TOOL EXECUTION GATE
# ============================================================================

def execute_tool_with_gate(llm_proposal: dict, kernel: ClarityKernel) -> None:
    """
    Evaluates LLM tool proposal through Clarity Kernel gate.

    The tool ONLY executes if the kernel returns ALLOWED.

    This demonstrates the core principle:
        The LLM proposes. The kernel decides.

    Args:
        llm_proposal: LLM's proposed tool call
        kernel: Clarity Kernel instance
    """
    print("\n" + "=" * 70)
    print(f"LLM PROPOSAL: {llm_proposal['tool']}")
    print(f"Arguments: {llm_proposal['arguments']}")
    print(f"Context: {llm_proposal['context']}")
    print("=" * 70)

    # Step 1: Convert LLM proposal to PermissionRequest
    request = build_permission_request(llm_proposal)

    print("\n[KERNEL] Evaluating permission request...")
    print(f"[KERNEL] Operation: {request.operation_id}")
    print(f"[KERNEL] Variables: {[(v.name, v.resolved, v.value) for v in request.variables]}")
    print(f"[KERNEL] Authority: {request.authority.source if request.authority else 'NONE'}")

    try:
        # Step 2: Invoke Clarity Kernel
        # This is where the kernel evaluates all invariants
        response = kernel.request_permission(request)

        # Step 3: Permission granted - execute tool
        if response.granted:
            print("\n[KERNEL] ✓ PERMISSION GRANTED")
            print(f"[KERNEL]   Control mode: {response.control_mode.value}")
            print(f"[KERNEL]   Interface width: w={response.measured_w}")
            print(f"[KERNEL]   Satisfied invariants: {sorted(response.satisfied_invariants)}")
            print("\n[SYSTEM] Executing tool...")

            # THE TOOL ONLY EXECUTES IF KERNEL ALLOWS
            delete_file(llm_proposal["arguments"]["path"])

            print("\n[SYSTEM] Tool execution complete.")
        else:
            # This branch should not be reached if kernel raises exception
            print("\n[KERNEL] ✗ PERMISSION DENIED")
            print("[SYSTEM] Tool execution blocked.")

    except PermissionDenied as e:
        # Step 3 (alternate): Permission denied - block execution
        print("\n[KERNEL] ✗ PERMISSION DENIED")
        print(f"[KERNEL]   Reason: {e.reason}")
        print(f"[KERNEL]   State: {e.kernel_state}")
        print("\n[SYSTEM] Tool execution BLOCKED by kernel.")
        print("[SYSTEM] The LLM's proposal was rejected.")
        print(f"[SYSTEM] Denial reason: {e.reason}")


# ============================================================================
# MAIN DEMONSTRATION
# ============================================================================

def main():
    """
    Demonstrates LLM tool gating with three scenarios:
    1. Valid proposal → ALLOWED → tool executes
    2. Ambiguous proposal → BLOCKED by I-1 (Clarity Invariant)
    3. No authority → BLOCKED by I-2 (Authority Invariant)
    """
    print("\n" + "=" * 70)
    print("CLARITY KERNEL: LLM TOOL CALL GATING DEMONSTRATION")
    print("=" * 70)
    print("\nPrinciple: LLMs may propose actions.")
    print("           The Clarity Kernel decides whether they happen.")
    print("\n" + "=" * 70)

    # Initialize Clarity Kernel
    kernel = ClarityKernel()

    # ========================================================================
    # SCENARIO 1: Valid proposal - all conditions met
    # ========================================================================
    print("\n\nSCENARIO 1: Valid Tool Proposal")
    print("-" * 70)
    print("Expected: ALLOWED (all invariants satisfied)")
    execute_tool_with_gate(llm_proposal_valid, kernel)

    # ========================================================================
    # SCENARIO 2: Ambiguous proposal - violates I-1 (Clarity Invariant)
    # ========================================================================
    print("\n\nSCENARIO 2: Ambiguous Tool Proposal")
    print("-" * 70)
    print("Expected: BLOCKED by I-1 (Clarity Invariant)")
    execute_tool_with_gate(llm_proposal_ambiguous, kernel)

    # ========================================================================
    # SCENARIO 3: No authority - violates I-2 (Authority Invariant)
    # ========================================================================
    print("\n\nSCENARIO 3: No Authority Provided")
    print("-" * 70)
    print("Expected: BLOCKED by I-2 (Authority Invariant)")
    execute_tool_with_gate(llm_proposal_no_auth, kernel)

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nThe Clarity Kernel evaluated 3 LLM tool proposals:")
    print("  1. ✓ ALLOWED  - All invariants satisfied, tool executed")
    print("  2. ✗ BLOCKED  - Clarity Invariant violated (ambiguous path)")
    print("  3. ✗ BLOCKED  - Authority Invariant violated (no permission)")
    print("\nKey takeaway:")
    print("  The kernel is the final authority, not the LLM.")
    print("  Tools execute ONLY when the kernel grants permission.")
    print("  STOP means STOP - no exceptions, no retries, no bypasses.")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
