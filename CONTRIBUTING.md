# Contributing to Clarity Kernel

Thank you for your interest in contributing.

Clarity Kernel is a safety-critical framework. Contributions are welcome, but
must preserve the core principles of clarity, determinism, and authority
boundaries.

---

## Core Principles (Non-Negotiable)

When contributing, you must respect the following:

- STOP is a valid and preferred outcome
- Ambiguity must never be resolved by guessing
- Capability never implies authority
- Invariants must not be softened
- The Stable Structural Layer (SSL) is deterministic and stateless
- Interaction logic must live outside SSL

If a proposed change violates any of the above, it will not be accepted.

---

## Project Structure

- `src/clarity_kernel/` — core framework
- `tests/` — unit tests (required for all logic changes)
- `examples/` — non-normative usage examples
- `SPECIFICATION.md` — canonical specification (authoritative)

The specification is the source of truth.

---

## Running Tests

```bash
pip install -e .
pip install pytest
pytest
```

All tests must pass before submitting a pull request.

---

## Adding New Invariants

If you add a new invariant:
- It must be explicitly defined
- It must be deterministic
- It must fail closed (STOP on violation)
- It must include tests
- It must be documented in SPECIFICATION.md

---

## Adding Examples

Examples must:
- Live in the examples/ directory
- Never bypass the kernel
- Never auto-execute actions
- Treat external systems (LLMs, tools, APIs) as non-authoritative

Examples are illustrative only and do not define kernel behavior.

---

## Pull Requests

When opening a pull request:
- Clearly state intent
- Reference the relevant spec section if applicable
- Explain why STOP behavior is preserved
- Avoid speculative or heuristic logic

Pull requests that weaken clarity or authority boundaries will be rejected.

---

## Questions

If you are unsure whether a change belongs in SSL or outside it, assume it does
not belong in SSL and ask first.

Clarity comes before convenience.
