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


if __name__ == "__main__":
    unittest.main()
