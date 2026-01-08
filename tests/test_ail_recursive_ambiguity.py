from clarity_kernel.ssl import ClarityKernel
from clarity_kernel.ail import AILWrapper, AILSession, TERMINAL_AMBIGUITY_TEXT
from clarity_kernel.types import PermissionRequest, Scope


def ambiguous_request():
    return PermissionRequest(
        operation="delete_file",
        variables={"path": "/important/data.csv"},
        required_definitions={"path", "allowed_directory"},
        required_constraints={"path": "Must be within an allowed directory"},
        authority_token="UNVERIFIED_LLM",
        scope=Scope.DESTRUCTIVE,
    )


def resolved_request():
    return PermissionRequest(
        operation="delete_file",
        variables={"path": "/safe/data.csv"},
        required_definitions={"path"},
        required_constraints={"path": "Within allowed directory"},
        authority_token="HUMAN_APPROVED",
        scope=Scope.DESTRUCTIVE,
    )


def test_recursive_ambiguity_terminates():
    kernel = ClarityKernel()
    session = AILSession(max_clarifications=2)
    ail = AILWrapper(kernel, session)

    # First ambiguous input → clarification
    r1 = ail.step(ambiguous_request())
    assert isinstance(r1, str)
    assert "provide the missing" in r1.lower()

    # Second ambiguous input → clarification
    r2 = ail.step(ambiguous_request())
    assert isinstance(r2, str)
    assert "provide the missing" in r2.lower()

    # Third ambiguous input → terminal ambiguity declaration
    r3 = ail.step(ambiguous_request())
    assert r3 == TERMINAL_AMBIGUITY_TEXT

    # Further ambiguous input → silence
    r4 = ail.step(ambiguous_request())
    assert r4 == ""


def test_ambiguity_resolution_resets_session():
    kernel = ClarityKernel()
    session = AILSession(max_clarifications=2)
    ail = AILWrapper(kernel, session)

    # Trigger ambiguity
    ail.step(ambiguous_request())

    # Resolve ambiguity
    decision = ail.step(resolved_request())

    # Session should reset and pass through kernel decision
    assert decision is not None
    assert not session.terminal_declared
    assert session.clarification_attempts == 0
