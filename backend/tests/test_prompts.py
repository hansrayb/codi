"""Prompt construction tests for task-specific guidance."""

from __future__ import annotations

import unittest

from core.prompts import build_chat_prompt, build_task_prompt


class PromptBuilderTests(unittest.TestCase):
    """Validate prompt instructions added for git workflow assistance."""

    def test_builder_prompt_includes_git_workflow_guidance(self) -> None:
        prompt = build_task_prompt(role="builder", user_prompt="buat commit message")
        self.assertIn("commit messages", prompt)
        self.assertIn("PR titles", prompt)
        self.assertIn("Do not push, merge, or publish anything", prompt)

    def test_reviewer_prompt_mentions_diff_review_context(self) -> None:
        prompt = build_task_prompt(role="reviewer", user_prompt="review PR ini")
        self.assertIn("review a diff, commit, or PR", prompt)
        self.assertIn("actual local changes", prompt)

    def test_chat_prompt_stays_non_executing(self) -> None:
        prompt = build_chat_prompt(user_prompt="bahas ide onboarding")
        self.assertIn("chat mode", prompt)
        self.assertIn("Do not modify files", prompt)
        self.assertIn("send that as a normal message outside /chat", prompt)

    def test_advisor_prompt_has_tone_directive_always(self) -> None:
        prompt = build_task_prompt(role="advisor", user_prompt="halo")
        self.assertIn("GAYA SAPAAN", prompt)
        self.assertIn("'kamu'", prompt)
        self.assertIn("JANGAN gunakan 'Bapak', 'Ibu', 'Anda'", prompt)

    def test_general_prompt_has_tone_directive_always(self) -> None:
        prompt = build_task_prompt(role="general", user_prompt="halo")
        self.assertIn("GAYA SAPAAN", prompt)

    def test_user_first_name_injected_when_provided(self) -> None:
        prompt = build_task_prompt(
            role="advisor", user_prompt="halo", user_first_name="Hans",
        )
        self.assertIn("User yang kamu ajak bicara bernama Hans", prompt)
        self.assertIn("Sapa dengan nama itu saat natural", prompt)

    def test_user_first_name_absent_when_empty(self) -> None:
        prompt = build_task_prompt(role="advisor", user_prompt="halo")
        self.assertNotIn("User yang kamu ajak bicara bernama", prompt)
        # Directive sapaan tetap muncul walaupun nama tak diketahui.
        self.assertIn("GAYA SAPAAN", prompt)

    def test_user_first_name_strips_whitespace(self) -> None:
        prompt = build_task_prompt(
            role="advisor", user_prompt="halo", user_first_name="  Hans  ",
        )
        self.assertIn("User yang kamu ajak bicara bernama Hans", prompt)


if __name__ == "__main__":
    unittest.main()
