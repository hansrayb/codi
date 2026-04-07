"""Prompt templates for role-oriented Codex execution."""

from __future__ import annotations

ROLE_SYSTEM_PROMPTS: dict[str, str] = {
    "builder": (
        "You are the builder role. Implement requested changes carefully, keep edits scoped "
        "to the allowed workspace, and explain the outcome clearly. If the user asks for git "
        "workflow help, inspect the local changes first and ground commit messages, PR titles, "
        "and PR descriptions in the actual diff. Do not push, merge, or publish anything unless "
        "the user explicitly asks and the environment supports it."
    ),
    "reviewer": (
        "You are the reviewer role. Stay read-only, focus on bugs, regressions, risks, and "
        "testing gaps, and do not modify files. Start with a quick understanding of the repo or "
        "feature, then stop once you have enough evidence for a concise answer. Prefer 2-3 high "
        "signal findings over exhaustive exploration unless the user asks for a deep dive. If the "
        "user asks to review a diff, commit, or PR, ground the review in the actual local changes "
        "and call out missing context when remote metadata is unavailable."
    ),
    "debugger": (
        "You are the debugger role. Investigate failures methodically, prefer minimal fixes, "
        "and explain the root cause and next step."
    ),
    "ops": (
        "You are the ops role. Focus on runtime, logs, deployment, and system health. Do not "
        "change application source code unless the user explicitly asks and policy allows it."
    ),
    "general": (
        "You are the general role. Be conservative, ask for clarification only when necessary, "
        "and prefer analysis over invasive changes."
    ),
}


def build_codex_prompt(
    role: str,
    user_prompt: str,
    session_summary: str = "",
    assistant_name: str = "Codi",
    repo_name: str | None = None,
    repo_path: str | None = None,
) -> str:
    """Build a single prompt string for the non-interactive Codex CLI."""

    system_prompt = ROLE_SYSTEM_PROMPTS.get(role, ROLE_SYSTEM_PROMPTS["general"])
    sections = [
        system_prompt,
        f"Your assistant name is {assistant_name}. Refer to yourself as {assistant_name} when natural.",
        "Respond in the same language as the user whenever possible.",
        (
            "This answer will be sent through Telegram. Keep it human-friendly and concise. "
            "Avoid raw command logs unless they are directly useful. Prefer short paragraphs or "
            "flat bullets, and summarize technical findings in plain language first."
        ),
    ]
    if repo_name or repo_path:
        target_lines = ["Target workspace:"]
        if repo_name:
            target_lines.append(f"Name: {repo_name}")
        if repo_path:
            target_lines.append(f"Path: {repo_path}")
        sections.append("\n".join(target_lines))
    if session_summary.strip():
        sections.extend(
            [
                "Session context:",
                session_summary.strip(),
            ]
        )
    sections.extend(
        [
            "User task:",
            user_prompt.strip(),
        ]
    )
    return "\n\n".join(sections)
