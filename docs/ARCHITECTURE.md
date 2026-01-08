# Clarity Kernel Architecture

This document describes the high-level architecture of the Clarity Kernel and
its separation of responsibilities.

---

## Layered Model

Clarity Kernel is intentionally split into two conceptual layers:

[ External System / LLM / User ]
|
v
Adaptive Interaction Layer (AIL)
|
v
Stable Structural Layer (SSL)

Only the SSL is normative.

---

## Stable Structural Layer (SSL)

The SSL is the core of the Clarity Kernel.

Properties:
- Deterministic
- Stateless
- Non-interactive
- Authority-preserving
- Fail-closed

Responsibilities:
- Enforce invariants
- Evaluate PermissionRequests
- Return ALLOW or STOP decisions
- Never guess
- Never retry
- Never optimize around constraints

The SSL does not:
- Ask questions
- Track attempts
- Maintain conversational state
- Interpret intent

If ambiguity exists, the SSL returns STOP immediately.

---

## Adaptive Interaction Layer (AIL)

The AIL is optional and non-normative.

Properties:
- Stateful
- Interactive
- Non-authoritative
- Constrained by SSL decisions

Responsibilities:
- Invoke the SSL
- Interpret STOP(reason=ambiguity)
- Ask neutral clarification questions
- Enforce clarification budgets
- Terminate interaction cleanly when ambiguity persists

The AIL must never:
- Override SSL decisions
- Bypass invariants
- Execute actions without SSL approval
- Infer authority

AIL logic exists solely to manage interaction, not correctness.

---

## Authority Flow

Authority flows in one direction only:

Human Authority
↓
PermissionRequest
↓
SSL

Neither the AIL nor external systems (LLMs, tools, APIs) possess authority.

---

## STOP Semantics

STOP is not an error.

STOP indicates that execution is forbidden under current conditions.

Reasons for STOP include (non-exhaustive):
- Ambiguity
- Missing authority
- Interface width violations
- Invariant failure

STOP outcomes are final unless a materially different request is submitted.

---

## Design Principle

If clarity, correctness, and authority cannot all be preserved simultaneously,
the system must stop.

This is a design choice, not a limitation.
