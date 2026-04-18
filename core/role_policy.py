"""Role policy definitions for orchestrated Codex execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RolePolicy:
    """Execution policy for a logical role."""

    name: str
    sandbox_mode: str
    allow_write: bool
    description: str


ROLE_POLICIES: dict[str, RolePolicy] = {
    "builder": RolePolicy(
        name="builder",
        sandbox_mode="workspace-write",
        allow_write=True,
        description="Implementation and code changes.",
    ),
    "reviewer": RolePolicy(
        name="reviewer",
        sandbox_mode="read-only",
        allow_write=False,
        description="Read-only code review and audit.",
    ),
    "debugger": RolePolicy(
        name="debugger",
        sandbox_mode="workspace-write",
        allow_write=True,
        description="Investigation and limited fixes.",
    ),
    "ops": RolePolicy(
        name="ops",
        sandbox_mode="read-only",
        allow_write=False,
        description="Operational diagnostics and status inspection.",
    ),
    "general": RolePolicy(
        name="general",
        sandbox_mode="read-only",
        allow_write=False,
        description="Safe fallback for ambiguous prompts.",
    ),
}


def get_role_policy(role: str) -> RolePolicy:
    """Return the policy for a role, falling back to the safest default."""

    return ROLE_POLICIES.get(role, ROLE_POLICIES["general"])
