"""Tests for persistent draft approval, apply, and rejection flows."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.edit_approval import EditApprovalError, EditApprovalManager


class EditApprovalManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate case-scoped draft reuse and approval behavior."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name).resolve() / "repo"
        self.repo_root.mkdir(parents=True)
        (self.repo_root / "src").mkdir()
        (self.repo_root / "src" / "app.py").write_text("print('before')\n", encoding="utf-8")
        (self.repo_root / "README.md").write_text("before\n", encoding="utf-8")
        self.manager = EditApprovalManager(ttl_minutes=30, draft_ttl_seconds=3600)

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    def test_control_message_classification(self) -> None:
        self.assertEqual(self.manager.classify_control_message("lanjutkan"), "approve")
        self.assertEqual(self.manager.classify_control_message("batal"), "reject")
        self.assertIsNone(self.manager.classify_control_message("lanjutkan review auth"))

    async def test_open_or_reuse_draft_returns_same_workspace(self) -> None:
        draft_one = await self.manager.open_or_reuse_draft(
            user_id=1,
            case_id="c-01",
            repo_root=self.repo_root,
        )
        draft_two = await self.manager.open_or_reuse_draft(
            user_id=1,
            case_id="c-01",
            repo_root=self.repo_root,
        )

        self.assertEqual(draft_one.draft_root, draft_two.draft_root)
        self.assertTrue((draft_one.draft_root / "src" / "app.py").exists())

    async def test_build_pending_and_approve_applies_changes(self) -> None:
        draft = await self.manager.open_or_reuse_draft(
            user_id=1,
            case_id="c-01",
            repo_root=self.repo_root,
        )
        (draft.draft_root / "src" / "app.py").write_text("print('after')\n", encoding="utf-8")
        (draft.draft_root / "src" / "new_module.py").write_text("value = 1\n", encoding="utf-8")
        (draft.draft_root / "README.md").unlink()

        pending = await self.manager.build_pending(
            case_id="c-01",
            user_id=1,
            role="builder",
            repo_root=self.repo_root,
            prompt="ubah app.py",
            draft_root=draft.draft_root,
            execution_output="Saya memperbarui app.py dan menambah module baru.",
        )

        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(len(pending.changes), 3)
        approved = await self.manager.approve(1)

        self.assertEqual(approved.approval_id, pending.approval_id)
        self.assertEqual(
            (self.repo_root / "src" / "app.py").read_text(encoding="utf-8"),
            "print('after')\n",
        )
        self.assertTrue((self.repo_root / "src" / "new_module.py").exists())
        self.assertFalse((self.repo_root / "README.md").exists())
        self.assertTrue((draft.draft_root / "src" / "new_module.py").exists())

    async def test_reject_resets_persistent_draft_and_clears_thread(self) -> None:
        draft = await self.manager.open_or_reuse_draft(
            user_id=7,
            case_id="c-07",
            repo_root=self.repo_root,
        )
        draft.codex_thread_id = "thread-edit-1"
        (draft.draft_root / "src" / "app.py").write_text("print('draft')\n", encoding="utf-8")

        pending = await self.manager.build_pending(
            case_id="c-07",
            user_id=7,
            role="builder",
            repo_root=self.repo_root,
            prompt="ubah app.py",
            draft_root=draft.draft_root,
            execution_output="Saya hanya menyiapkan draft.",
        )

        self.assertIsNotNone(pending)
        rejected = await self.manager.reject(7)
        self.assertEqual(rejected.role, "builder")
        self.assertEqual(
            (self.repo_root / "src" / "app.py").read_text(encoding="utf-8"),
            "print('before')\n",
        )
        self.assertEqual(
            (draft.draft_root / "src" / "app.py").read_text(encoding="utf-8"),
            "print('before')\n",
        )
        self.assertIsNone(draft.codex_thread_id)

    async def test_approve_detects_conflict_on_original_repo(self) -> None:
        draft = await self.manager.open_or_reuse_draft(
            user_id=9,
            case_id="c-09",
            repo_root=self.repo_root,
        )
        draft.codex_thread_id = "thread-edit-2"
        (draft.draft_root / "src" / "app.py").write_text("print('after')\n", encoding="utf-8")

        pending = await self.manager.build_pending(
            case_id="c-09",
            user_id=9,
            role="builder",
            repo_root=self.repo_root,
            prompt="ubah app.py",
            draft_root=draft.draft_root,
            execution_output="Saya menyiapkan update app.py.",
        )
        self.assertIsNotNone(pending)

        (self.repo_root / "src" / "app.py").write_text("print('outside change')\n", encoding="utf-8")

        with self.assertRaises(EditApprovalError):
            await self.manager.approve(9)

        self.assertEqual(
            (draft.draft_root / "src" / "app.py").read_text(encoding="utf-8"),
            "print('outside change')\n",
        )
        self.assertIsNone(draft.codex_thread_id)

    async def test_close_case_discards_draft_workspace(self) -> None:
        draft = await self.manager.open_or_reuse_draft(
            user_id=3,
            case_id="c-03",
            repo_root=self.repo_root,
        )
        draft_root = draft.draft_root

        await self.manager.close_case("c-03")

        self.assertFalse(draft_root.exists())


if __name__ == "__main__":
    unittest.main()
