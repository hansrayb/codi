"""Test agent_messaging store (send/inbox/wait_reply/history)."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from core.agent_messaging import AgentMessagingStore


class AgentMessagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = AgentMessagingStore.connect(
            Path(self._tmp.name) / "msg.db"
        )

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_send_and_inbox(self) -> None:
        sent = self.store.send(
            sender="laptop", recipient="server", content="halo"
        )
        self.assertTrue(sent["id"])
        inbox = self.store.inbox("server")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["content"], "halo")
        # Sudah di-mark read → inbox berikutnya kosong.
        self.assertEqual(self.store.inbox("server"), [])

    def test_inbox_no_mark_read(self) -> None:
        self.store.send(sender="a", recipient="b", content="x")
        msgs = self.store.inbox("b", mark_read=False)
        self.assertEqual(len(msgs), 1)
        again = self.store.inbox("b", mark_read=False)
        self.assertEqual(len(again), 1)

    def test_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.store.send(sender="", recipient="b", content="x")
        with self.assertRaises(ValueError):
            self.store.send(sender="a", recipient="b", content="   ")

    def test_thread_history(self) -> None:
        self.store.send(sender="a", recipient="b", content="1", thread_id="t1")
        self.store.send(sender="b", recipient="a", content="2", thread_id="t1")
        self.store.send(sender="a", recipient="b", content="3", thread_id="t2")
        h = self.store.history(thread_id="t1")
        self.assertEqual([m["content"] for m in h], ["1", "2"])

    def test_pairwise_history(self) -> None:
        self.store.send(sender="a", recipient="b", content="x")
        self.store.send(sender="b", recipient="a", content="y")
        self.store.send(sender="c", recipient="a", content="z")
        h = self.store.history(peer_a="a", peer_b="b")
        self.assertEqual({m["content"] for m in h}, {"x", "y"})

    def test_wait_reply_timeout(self) -> None:
        result = self.store.wait_reply(
            recipient="server", timeout_seconds=1, poll_interval=0.1
        )
        self.assertIsNone(result)

    def test_wait_reply_receives_new(self) -> None:
        def producer() -> None:
            time.sleep(0.2)
            self.store.send(
                sender="laptop", recipient="server", content="ack"
            )

        threading.Thread(target=producer, daemon=True).start()
        msg = self.store.wait_reply(
            recipient="server", timeout_seconds=3, poll_interval=0.1
        )
        self.assertIsNotNone(msg)
        self.assertEqual(msg["content"], "ack")

    def test_wait_reply_thread_filter(self) -> None:
        # Pesan di thread lain harus diabaikan.
        self.store.send(
            sender="a", recipient="b", content="other", thread_id="other"
        )

        def producer() -> None:
            time.sleep(0.2)
            self.store.send(
                sender="a", recipient="b", content="target", thread_id="t1"
            )

        threading.Thread(target=producer, daemon=True).start()
        msg = self.store.wait_reply(
            recipient="b",
            thread_id="t1",
            timeout_seconds=2,
            poll_interval=0.1,
        )
        self.assertIsNotNone(msg)
        self.assertEqual(msg["content"], "target")

    def test_list_threads_and_agents(self) -> None:
        self.store.send(sender="a", recipient="b", content="x", thread_id="t1")
        self.store.send(sender="b", recipient="c", content="y", thread_id="t2")
        threads = self.store.list_threads()
        self.assertEqual({t["thread_id"] for t in threads}, {"t1", "t2"})
        agents = self.store.list_agents()
        self.assertEqual(set(agents), {"a", "b", "c"})


if __name__ == "__main__":
    unittest.main()
