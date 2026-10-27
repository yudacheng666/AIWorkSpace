"""Independent-data tests for the first AIWorkSpace task loop."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import append_event, handler_factory, read_workspace, validate_event  # noqa: E402


def event(event_id="demo-event-001", task_id="TASK-DEMO-001", action="create",
          revision=0, changes=None, actor="chatgpt", **other):
    return {"version": 1, "event_id": event_id, "task_id": task_id,
            "action": action, "actor": actor, "base_revision": revision,
            "timestamp": "2026-10-27T00:00:00Z",
            "changes": changes or {"title": "虚构测试任务", "status": "todo"}, **other}


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty(self):
        self.assertEqual(read_workspace(self.data_dir), {"tasks": [], "warnings": []})

    def test_chatgpt_creation_survives_reload(self):
        append_event(self.data_dir, event())
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["revision"], 1)

    def test_user_edit_preserves_original(self):
        original = append_event(self.data_dir, event())
        original_bytes = original.read_bytes()
        append_event(self.data_dir, event("demo-event-002", action="update", revision=1,
                                           actor="user", changes={"title": "调整后的虚构任务", "status": "doing"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual((task["title"], task["status"], task["revision"]),
                         ("调整后的虚构任务", "doing", 2))
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)

    def test_completion_requires_real_user_confirmation(self):
        append_event(self.data_dir, event())
        changed = event("demo-event-003", action="update", revision=1,
                        changes={"status": "done"})
        with self.assertRaises(ValueError):
            validate_event(changed)
        changed["actor"] = "user"
        with self.assertRaises(ValueError):
            validate_event(changed)
        changed["confirmed_done"] = True
        append_event(self.data_dir, changed)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "done")

    def test_concurrent_same_revision_stops_without_winner(self):
        append_event(self.data_dir, event())
        for number, title in ((2, "AI 建议"), (3, "网页决定")):
            append_event(self.data_dir, event(f"demo-event-00{number}", action="update",
                                               revision=1, actor="user",
                                               changes={"title": title}))
        state = read_workspace(self.data_dir)
        self.assertTrue(state["tasks"][0]["conflict"])
        self.assertEqual(state["tasks"][0]["title"], "虚构测试任务")
        self.assertEqual(state["tasks"][0]["revision"], 1)
        self.assertTrue(any("conflicting" in message for message in state["warnings"]))

    def test_late_create_file_is_reconstructed_in_correct_order(self):
        append_event(self.data_dir, event("demo-event-004", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 0)
        append_event(self.data_dir, event())
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "doing")

    def test_corrupted_file_is_reported(self):
        (self.data_dir / "events").mkdir()
        (self.data_dir / "events" / "broken.json").write_text("{not valid json}", encoding="utf-8")
        self.assertTrue(read_workspace(self.data_dir)["warnings"])

    def test_duplicate_event_id_is_reported(self):
        append_event(self.data_dir, event())
        (self.data_dir / "events" / "duplicate.json").write_text(json.dumps(event()), encoding="utf-8")
        state = read_workspace(self.data_dir)
        self.assertEqual(len(state["tasks"]), 1)
        self.assertTrue(any("duplicate" in w for w in state["warnings"]))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        append_event(self.data_dir, event())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, body):
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update",
                          data=json.dumps(body).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_webpage_and_api_available(self):
        with urlopen(self.base + "/", timeout=3) as response:
            self.assertIn("AIWorkSpace", response.read().decode("utf-8"))
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            self.assertEqual(json.load(response)["tasks"][0]["title"], "虚构测试任务")

    def test_http_save_then_read(self):
        status, result = self.request({"title": "网页更新", "status": "doing", "revision": 1})
        self.assertEqual(status, 200)
        self.assertTrue(result["saved"])
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            self.assertEqual(json.load(response)["tasks"][0]["title"], "网页更新")

    def test_stale_revision_cannot_overwrite(self):
        self.request({"title": "第一次", "status": "doing", "revision": 1})
        status, _ = self.request({"title": "过期写入", "status": "blocked", "revision": 1})
        self.assertEqual(status, 409)

    def test_web_cannot_complete_without_confirmation(self):
        status, _ = self.request({"title": "虚构测试任务", "status": "done", "revision": 1})
        self.assertEqual(status, 400)
        status, _ = self.request({"title": "虚构测试任务", "status": "done",
                                  "revision": 1, "confirmed_done": True})
        self.assertEqual(status, 200)

    def test_user_can_edit_title_after_completion(self):
        status, _ = self.request({"title": "虚构测试任务", "status": "done",
                                  "revision": 1, "confirmed_done": True})
        self.assertEqual(status, 200)
        status, _ = self.request({"title": "已完成事项的备注调整", "status": "done",
                                  "revision": 2, "confirmed_done": True})
        self.assertEqual(status, 200)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "已完成事项的备注调整")

    def test_external_origin_cannot_update(self):
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update",
                          data=json.dumps({"title": "被拒绝", "status": "doing", "revision": 1}).encode(),
                          method="POST", headers={"Content-Type": "application/json",
                                                  "Origin": "https://untrusted.example"})
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 403)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")

    def test_synced_chatgpt_event_becomes_visible_without_restart(self):
        second = event("demo-event-005", "TASK-DEMO-002", changes={"title": "第二个虚构事项"})
        append_event(self.data_dir, second)
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            tasks = json.load(response)["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[1]["title"], "第二个虚构事项")


if __name__ == "__main__":
    unittest.main()
