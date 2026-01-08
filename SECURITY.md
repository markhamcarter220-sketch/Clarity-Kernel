# Security Policy

Clarity Kernel is a safety-critical framework. Security issues are treated as
correctness issues, not feature requests.

---

## Supported Versions

Only the latest released version is supported.

Unreleased development branches may change invariants and should not be relied
upon for security guarantees.

---

## Reporting a Vulnerability

If you believe you have found a security issue, invariant bypass, authority
leak, or STOP-softening behavior:

- Do NOT open a public issue.
- Do NOT post a proof publicly.
- Contact the repository owner directly.

Provide:
- A clear description of the issue
- Steps to reproduce
- Why the behavior violates an invariant or authority boundary
- Any suggested mitigation (optional)

---

## What Counts as a Security Issue

Examples include:
- Execution allowed under ambiguity
- Authority inferred rather than explicitly provided
- Invariants that can be bypassed or weakened
- State leakage across kernel evaluations
- Non-deterministic behavior in SSL

---

## What Does NOT Count as a Security Issue

- Missing features
- Requests for convenience behavior
- Requests to relax STOP semantics
- Requests to "make the kernel smarter"
- Behavior that correctly results in STOP

STOP is a valid and correct outcome.

---

## Disclosure Philosophy

Clarity Kernel follows responsible disclosure practices.

Issues will be investigated, fixed if valid, and documented in release notes.
No timelines are guaranteed.

Clarity and safety take precedence over speed.
