"""Independent-data tests for the first AIWorkSpace task loop."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as app_module  # noqa: E402
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

    def test_utf8_bom_event_from_external_writer_is_readable(self):
        events = self.data_dir / "events"
        events.mkdir()
        payload = json.dumps(event(
            "external-bom-event",
            task_id="TASK-EXTERNAL-BOM",
            changes={"title": "外部写入的虚构测试任务", "status": "todo"},
        ), ensure_ascii=False, indent=2)
        (events / "evt_external-bom-event.json").write_text(
            payload, encoding="utf-8-sig"
        )
        state = read_workspace(self.data_dir)
        self.assertEqual(state["warnings"], [])
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0]["task_id"], "TASK-EXTERNAL-BOM")
        self.assertEqual(state["tasks"][0]["title"], "外部写入的虚构测试任务")
        self.assertEqual(state["tasks"][0]["status"], "todo")

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
        self.assertEqual(state["tasks"][0]["conflict_fields"], ["title"])
        self.assertEqual(len(state["tasks"][0]["conflict_candidates"]), 2)
        self.assertTrue(any("conflicting" in message for message in state["warnings"]))

    def test_conflicting_status_values_are_explicitly_exposed(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-006", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        append_event(self.data_dir, event("demo-event-007", action="update", revision=1,
                                           actor="chatgpt", changes={"status": "blocked"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(task["conflict"])
        self.assertEqual(task["status"], "todo")  # base state only; UI must not present it as resolved
        self.assertEqual(task["conflict_fields"], ["status"])
        self.assertEqual(
            {candidate["changes"]["status"] for candidate in task["conflict_candidates"]},
            {"doing", "blocked"},
        )

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

    def test_concurrent_same_event_id_never_overwrites_existing_event(self):
        first = event("demo-event-099", changes={"title": "并发写入甲", "status": "todo"})
        second = event("demo-event-099", changes={"title": "并发写入乙", "status": "todo"})
        barrier = threading.Barrier(2)
        original_link = app_module.os.link
        outcomes = []
        outcomes_lock = threading.Lock()

        def synchronized_link(source, destination):
            # Force both writers to reach the atomic publication point together.
            barrier.wait(timeout=3)
            return original_link(source, destination)

        def writer(value):
            try:
                path = append_event(self.data_dir, value)
                result = ("success", json.loads(path.read_text(encoding="utf-8"))["changes"]["title"])
            except Exception as exc:  # capture thread result for assertions in the main thread
                result = ("error", type(exc).__name__)
            with outcomes_lock:
                outcomes.append(result)

        with patch("app.os.link", side_effect=synchronized_link):
            threads = [threading.Thread(target=writer, args=(value,)) for value in (first, second)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "writer thread hung")
        self.assertEqual(sum(result[0] == "success" for result in outcomes), 1, outcomes)
        self.assertEqual(sum(result == ("error", "FileExistsError") for result in outcomes), 1, outcomes)
        files = list((self.data_dir / "events").glob("evt_demo-event-099.json"))
        self.assertEqual(len(files), 1)
        stored = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertIn(stored["changes"]["title"], {"并发写入甲", "并发写入乙"})

    def test_duplicate_event_id_with_different_content_freezes_task(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-008", action="update", revision=1,
                                           changes={"status": "doing"}))
        conflicting = event("demo-event-008", action="update", revision=1,
                            changes={"status": "blocked"})
        (self.data_dir / "events" / "z_duplicate.json").write_text(
            json.dumps(conflicting), encoding="utf-8"
        )
        state = read_workspace(self.data_dir)
        task = state["tasks"][0]
        self.assertTrue(task["conflict"])
        self.assertEqual(task["conflict_fields"], ["status"])
        self.assertEqual(
            {candidate["changes"]["status"] for candidate in task["conflict_candidates"]},
            {"doing", "blocked"},
        )
        self.assertTrue(any("conflicting content" in warning for warning in state["warnings"]))

    def test_duplicate_event_id_across_tasks_freezes_both_tasks(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-009", task_id="TASK-DEMO-002",
                                          changes={"title": "第二个虚构任务", "status": "todo"}))
        append_event(self.data_dir, event("demo-event-010", task_id="TASK-DEMO-001",
                                          action="update", revision=1,
                                          changes={"status": "doing"}))
        conflicting = event("demo-event-010", task_id="TASK-DEMO-002",
                            action="update", revision=1, changes={"status": "blocked"})
        (self.data_dir / "events" / "z_cross_task_duplicate.json").write_text(
            json.dumps(conflicting), encoding="utf-8"
        )
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertTrue(tasks["TASK-DEMO-001"]["conflict"])
        self.assertTrue(tasks["TASK-DEMO-002"]["conflict"])


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

    def create_task(self, body, extra_headers=None, content_type="application/json"):
        headers = {"Content-Type": content_type}
        headers.update(extra_headers or {})
        request = Request(self.base + "/api/tasks",
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_create_task_success_and_persists(self):
        status, result = self.create_task({"title": "  新任务：安排资料整理  "})
        self.assertEqual(status, 201)
        self.assertTrue(result["saved"])
        self.assertEqual(result["revision"], 1)
        self.assertRegex(result["task_id"], r"^TASK-[A-F0-9]{32}$")
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual(tasks[result["task_id"]]["title"], "新任务：安排资料整理")
        self.assertEqual(tasks[result["task_id"]]["status"], "todo")
        self.assertEqual(tasks[result["task_id"]]["revision"], 1)
        self.assertFalse(tasks[result["task_id"]]["conflict"])
        created = [json.loads(p.read_text(encoding="utf-8"))
                   for p in (self.data_dir / "events").glob("*.json")
                   if json.loads(p.read_text(encoding="utf-8"))["task_id"] == result["task_id"]]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["action"], "create")
        self.assertEqual(created[0]["actor"], "user")
        self.assertEqual(created[0]["base_revision"], 0)
        self.assertEqual(created[0]["changes"], {"title": "新任务：安排资料整理",
                                                  "status": "todo"})
        with urlopen(self.base + "/api/tasks", timeout=3) as reply:
            self.assertIn(result["task_id"], {t["task_id"] for t in json.load(reply)["tasks"]})

    def test_create_rejects_invalid_payload_without_writing(self):
        invalid = [{"title": ""}, {"title": "   "}, {"title": "x" * 201},
                   {"title": 123}, {"title": "valid", "status": "done"},
                   {"title": "valid", "task_id": "TASK-INJECTED"},
                   {"title": "valid", "actor": "chatgpt"},
                   {"title": "valid", "base_revision": 1}]
        before = len(list((self.data_dir / "events").glob("*.json")))
        for payload in invalid:
            with self.subTest(payload=payload):
                status, _ = self.create_task(payload)
                self.assertEqual(status, 400)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), before)

    def test_create_rejects_untrusted_origin_and_host(self):
        before = len(list((self.data_dir / "events").glob("*.json")))
        for headers in ({"Origin": "https://untrusted.example"},
                        {"Host": "attacker.example"}):
            with self.subTest(headers=headers):
                status, response = self.create_task({"title": "never saved"}, headers)
                self.assertEqual(status, 403)
                self.assertIn("local requests only", response["error"])
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), before)

    def test_create_requires_json_content_type(self):
        status, _ = self.create_task({"title": "wrong mime"}, content_type="text/plain")
        self.assertEqual(status, 415)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)

    def test_create_handles_disk_publish_failure_without_phantom_task(self):
        with patch("app.os.link", side_effect=OSError("simulated write failure")):
            status, response = self.create_task({"title": "will not persist"})
        self.assertEqual(status, 500)
        self.assertEqual(response["error"], "unable to save event")
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 1)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)

    def test_create_concurrent_requests_get_distinct_ids(self):
        results = []
        lock = threading.Lock()

        def writer(value):
            result = self.create_task({"title": value})
            with lock:
                results.append(result)

        first = threading.Thread(target=writer, args=("Task one",))
        second = threading.Thread(target=writer, args=("Task two",))
        first.start()
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual([code for code, _ in results].count(201), 2, results)
        task_ids = [result["task_id"] for _, result in results]
        self.assertEqual(len(set(task_ids)), 2)
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual({tasks[tid]["title"] for tid in task_ids}, {"Task one", "Task two"})

    def test_webpage_and_api_available(self):
        with urlopen(self.base + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertIn("AIWorkSpace", html)
            self.assertIn("新建任务", html)
            self.assertIn('id="create-task"', html)
            self.assertIn("状态存在冲突（未裁决）", html)
            self.assertIn("冲突候选不是最终结论", html)
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            self.assertEqual(json.load(response)["tasks"][0]["title"], "虚构测试任务")

    def test_get_rejects_untrusted_host_headers(self):
        port = self.server.server_port
        for host in ("attacker.example", f"127.0.0.1:{port}.attacker.example",
                     f"localhost.attacker.example:{port}"):
            with self.subTest(host=host):
                request = Request(self.base + "/api/tasks", headers={"Host": host})
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=3)
                self.assertEqual(raised.exception.code, 403)
                self.assertIn("local requests only", raised.exception.read().decode("utf-8"))

    def test_localhost_host_header_is_allowed(self):
        host = f"localhost:{self.server.server_port}"
        request = Request(self.base + "/api/tasks", headers={"Host": host})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["tasks"][0]["title"], "虚构测试任务")

    def test_post_rejects_untrusted_host_header(self):
        body = json.dumps({"title": "不应保存", "status": "doing", "revision": 1}).encode("utf-8")
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update", data=body,
                          method="POST", headers={"Content-Type": "application/json",
                                                  "Host": "attacker.example"})
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 403)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")

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

    def test_api_rejects_write_when_task_has_unresolved_conflict(self):
        append_event(self.data_dir, event("demo-event-011", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        append_event(self.data_dir, event("demo-event-012", action="update", revision=1,
                                           actor="chatgpt", changes={"status": "blocked"}))
        before = len(list((self.data_dir / "events").glob("*.json")))
        status, _ = self.request({"title": "不应写入", "status": "todo", "revision": 1})
        after = len(list((self.data_dir / "events").glob("*.json")))
        self.assertEqual(status, 409)
        self.assertEqual(after, before)

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
