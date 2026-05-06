"""Tests for loading runtime settings from `.env` files."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from config import load_settings


class LoadSettingsTests(unittest.TestCase):
    """Validate `.env` loading behavior for runtime restarts."""

    def test_dotenv_overrides_stale_process_role_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve()
            env_path = workspace / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TELEGRAM_BOT_TOKEN=test-token",
                        "ALLOWED_USER_IDS=5354020279,8518719557",
                        "ADMIN_USER_IDS=5354020279,8518719557",
                        "VIEWER_USER_IDS=",
                        "BUSINESS_USER_IDS=",
                        f"CODEX_WORK_DIR={workspace}",
                        f"ALLOWED_WORK_DIRS={workspace}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            original_env = {
                key: os.environ.get(key)
                for key in (
                    "TELEGRAM_BOT_TOKEN",
                    "ALLOWED_USER_IDS",
                    "ADMIN_USER_IDS",
                    "VIEWER_USER_IDS",
                    "BUSINESS_USER_IDS",
                    "CODEX_WORK_DIR",
                    "ALLOWED_WORK_DIRS",
                )
            }
            try:
                os.environ["TELEGRAM_BOT_TOKEN"] = "stale-token"
                os.environ["ALLOWED_USER_IDS"] = "5354020279,8518719557"
                os.environ["ADMIN_USER_IDS"] = "5354020279"
                os.environ["VIEWER_USER_IDS"] = ""
                os.environ["BUSINESS_USER_IDS"] = "8518719557"
                os.environ["CODEX_WORK_DIR"] = str(workspace)
                os.environ["ALLOWED_WORK_DIRS"] = str(workspace)

                settings = load_settings(env_path)

                self.assertEqual(settings.admin_user_ids, (5354020279, 8518719557))
                self.assertEqual(settings.business_user_ids, ())
            finally:
                for key, value in original_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
