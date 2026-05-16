"""Tests for safe `.env` config updates from natural Telegram prompts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.env_config import (
    EnvConfigError,
    EnvConfigUpdateRequest,
    apply_env_config_update,
    match_env_config_update_query,
)


class EnvConfigQueryTests(unittest.TestCase):
    """Validate prompt matching for supported `.env` updates."""

    def test_natural_timeout_prompt_is_detected(self) -> None:
        request = match_env_config_update_query("ubah codex timeout jadi 600")
        self.assertEqual(
            request,
            EnvConfigUpdateRequest(
                key="CLAUDE_TIMEOUT",
                value="600",
                display_name="Codex timeout",
                original_prompt="ubah codex timeout jadi 600",
            ),
        )

    def test_direct_env_key_prompt_is_detected(self) -> None:
        request = match_env_config_update_query("set CLAUDE_TIMEOUT=900")
        self.assertEqual(
            request,
            EnvConfigUpdateRequest(
                key="CLAUDE_TIMEOUT",
                value="900",
                display_name="Codex timeout",
                original_prompt="set CLAUDE_TIMEOUT=900",
            ),
        )

    def test_local_shell_timeout_prompt_is_detected(self) -> None:
        request = match_env_config_update_query("ubah local shell timeout jadi 600")
        self.assertEqual(
            request,
            EnvConfigUpdateRequest(
                key="LOCAL_SHELL_TIMEOUT",
                value="600",
                display_name="Local shell timeout",
                original_prompt="ubah local shell timeout jadi 600",
            ),
        )

    def test_unknown_setting_is_ignored(self) -> None:
        self.assertIsNone(match_env_config_update_query("ubah telegram token jadi 123"))


class EnvConfigApplyTests(unittest.TestCase):
    """Validate `.env` file update behavior."""

    def test_existing_value_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("CLAUDE_TIMEOUT=180\nOTHER=value\n", encoding="utf-8")

            result = apply_env_config_update(
                EnvConfigUpdateRequest(
                    key="CLAUDE_TIMEOUT",
                    value="600",
                    display_name="Codex timeout",
                    original_prompt="ubah codex timeout jadi 600",
                ),
                env_path=env_path,
            )

            self.assertTrue(result.changed)
            self.assertEqual(result.old_value, "180")
            self.assertEqual(result.new_value, "600")
            self.assertIn("CLAUDE_TIMEOUT=600\n", env_path.read_text(encoding="utf-8"))

    def test_missing_value_is_appended(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("OTHER=value\n", encoding="utf-8")

            result = apply_env_config_update(
                EnvConfigUpdateRequest(
                    key="CLAUDE_TIMEOUT",
                    value="600",
                    display_name="Codex timeout",
                    original_prompt="ubah codex timeout jadi 600",
                ),
                env_path=env_path,
            )

            self.assertTrue(result.changed)
            self.assertIsNone(result.old_value)
            self.assertTrue(env_path.read_text(encoding="utf-8").endswith("CLAUDE_TIMEOUT=600\n"))

    def test_same_value_skips_write_semantically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("CLAUDE_TIMEOUT=600\n", encoding="utf-8")

            result = apply_env_config_update(
                EnvConfigUpdateRequest(
                    key="CLAUDE_TIMEOUT",
                    value="600",
                    display_name="Codex timeout",
                    original_prompt="ubah codex timeout jadi 600",
                ),
                env_path=env_path,
            )

            self.assertFalse(result.changed)
            self.assertEqual(result.old_value, "600")

    def test_invalid_value_is_rejected_during_matching(self) -> None:
        with self.assertRaises(EnvConfigError):
            match_env_config_update_query("ubah codex timeout jadi 0")

    def test_invalid_local_shell_timeout_is_rejected_during_matching(self) -> None:
        with self.assertRaises(EnvConfigError):
            match_env_config_update_query("ubah local shell timeout jadi 0")


if __name__ == "__main__":
    unittest.main()
