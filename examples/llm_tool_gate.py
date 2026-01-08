"""
Example: LLM Tool Gate using the Clarity Kernel

This example demonstrates how a Large Language Model (LLM) may PROPOSE
a tool invocation, but the Clarity Kernel is the final authority on
whether that tool is allowed to execute.

The LLM is non-authoritative.
The kernel decides.
"""

from clarity_kernel.ssl import ClarityKernel
from clarity_kernel.types import PermissionRequest, Scope


# ---------------------------------------------------------------------
# Fake tool (dangerous by default)
# ---------------------------------------------------------------------

def delete_file(path: str):
    print(f"[TOOL] Deleting file at: {path}")


# ---------------------------------------------------------------------
# Simulated LLM proposal
# ---------------------------------------------------------------------

llm_proposal = {
    "tool": "delete_file",
    "arguments": {
        "path": "/important/data.csv"
    }
}


# ---------------------------------------------------------------------
# Convert LLM proposal into a PermissionRequest
# ---------------------------------------------------------------------

request = PermissionRequest(
    operation="delete_file",
    variables=llm_proposal["arguments"],

    # Definitions and constraints required for safe execution
    required_definitions={"path"},
    required_constraints={
        "path": "Must be within an allowed directory"
    },

    # Placeholder authority token (LLM does NOT have authority)
    authority_token="UNVERIFIED_LLM",

    # File deletion is destructive by default
    scope=Scope.DESTRUCTIVE
)


# ---------------------------------------------------------------------
# Invoke the Clarity Kernel
# ---------------------------------------------------------------------

kernel = ClarityKernel()
decision = kernel.evaluate(request)


# ---------------------------------------------------------------------
# Enforce decision
# ---------------------------------------------------------------------

if decision.allowed:
    print("[GATE] Tool execution permitted by Clarity Kernel.")
    delete_file(**llm_proposal["arguments"])
else:
    print("[GATE] Tool execution BLOCKED by Clarity Kernel.")
    print(f"[REASON] {decision.reason}")
