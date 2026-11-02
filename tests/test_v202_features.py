"""V2.0.2 lifecycle, derived statuses and Google Drive links with fake data only."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app


def evt(identifier, action="create", revision=0, changes=None, task_id="TASK-FAKE-001",
        actor="user", timestamp="2026-10-01T00:00:00Z", **other):
    return {
        "version": 1, "event_id": identifier, "task_id": task_id,
        "action": action, "actor": actor, "timestamp": timestamp,
        "base_revision": revision,
        "changes": changes if changes is not None else {"title": "虚构任务", "status": "todo"},
        **other,
    }


def step(identifier, action="create", revision=0, changes=None,
         step_id="STEP-" + "A" * 32, task_id="TASK-FAKE-001", **other):
    return {
        "version": 1, "event_id": identifier, "task_id": task_id,
        "step_id": step_id, "action": action, "actor": "user",
        "base_revision": revision, "timestamp": "2026-10-01T00:00:00Z",
        "changes": changes if changes is not None else {"title": "虚构步骤", "position": 1},
        **other,
    }


class ReducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        app.append_event(self.data_dir, evt("fake-create-001"))

    def tearDown(self):
        self.temp.cleanup()

    def task(self):
        return app.read_workspace(self.data_dir, include_trashed=True)["tasks"][0]

    def test_trash_restore_is_append_only_and_default_hidden(self):
        app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                            {"trashed_at": "2026-10-01T01:00:00Z"}))
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"], [])
        trashed = self.task()
        self.assertEqual(trashed["revision"], 2)
        self.assertEqual(trashed["trashed_at"], "2026-10-01T01:00:00Z")
        app.append_event(self.data_dir, evt("fake-restore-001", "restore", 2,
                                            {"trashed_at": None}))
        restored = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(restored["revision"], 3)
        self.assertIsNone(restored["trashed_at"])
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 3)

    def test_purge_tombstone_prevents_resurrection_from_late_sync(self):
        app.append_step_event(self.data_dir, step("fake-step-001"))
        app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                            {"trashed_at": "2026-10-01T01:00:00Z"}))
        app.append_task_lifecycle(self.data_dir, self.task(), "purge")
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"], [])
        self.assertEqual(app.read_workspace(self.data_dir, include_trashed=True)["tasks"], [])
        remaining = list((self.data_dir / "events").glob("*.json"))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(json.loads(remaining[0].read_text("utf-8"))["action"], "purge")
        self.assertEqual(list((self.data_dir / "step_events").glob("*.json")), [])
        app.append_event(self.data_dir, evt("late-sync-create-123",
                                            changes={"title": "旧副本重现", "status": "todo"}))
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"], [])

    def test_duplicate_trash_and_restore_revision_is_frozen(self):
        app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                            {"trashed_at": "2026-10-01T01:00:00Z"}))
        app.append_event(self.data_dir, evt("fake-restore-001", "restore", 1,
                                            {"trashed_at": None}))
        task = self.task()
        self.assertTrue(task["conflict"])
        self.assertEqual(task["revision"], 1)

    def test_auto_retention_purges_when_accessed_but_off_never_purges(self):
        app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                            {"trashed_at": "2026-10-01T01:00:00Z"}))
        setting = {"version": 1, "event_id": "settings-off-001",
                   "key": "trash_retention_days", "days": 0,
                   "timestamp": "2026-11-01T01:00:00Z"}
        app._append_json_event(self.data_dir, setting, "settings_events")
        app.expire_trashed_tasks(self.data_dir)
        self.assertTrue(self.task()["trashed_at"])
        setting["event_id"] = "settings-on-001"
        setting["days"] = 7
        setting["timestamp"] = "2026-11-01T01:00:01Z"
        app._append_json_event(self.data_dir, setting, "settings_events")
        app.expire_trashed_tasks(self.data_dir)
        self.assertEqual(app.read_workspace(self.data_dir, include_trashed=True)["tasks"], [])

    def test_step_rollup_blocked_and_all_done_pending_user_confirmation(self):
        step_id = "STEP-" + "A" * 32
        app.append_step_event(self.data_dir, step("fake-step-001", step_id=step_id))
        app.append_step_event(self.data_dir, step("fake-step-002", action="update", revision=1,
                                                  changes={"status": "blocked"}, step_id=step_id))
        state = self.task()
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["manual_status"], "todo")
        self.assertEqual(state["status_source"], "steps")
        app.append_step_event(self.data_dir, step("fake-step-003", action="update", revision=2,
                                                  changes={"status": "done"}, step_id=step_id,
                                                  confirmed_done=True))
        state = self.task()
        self.assertEqual(state["status"], "doing")  # NEVER auto-done
        self.assertTrue(state["step_completion_pending"])
        app.append_event(self.data_dir, evt("fake-manual-done", "update", 1,
                                            {"status": "done"}, confirmed_done=True))
        state = self.task()
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["status_source"], "user_confirmed")
        self.assertFalse(state["step_completion_pending"])

    def test_conflicted_step_does_not_override_parent(self):
        sid = "STEP-" + "A" * 32
        app.append_step_event(self.data_dir, step("fake-step-001", step_id=sid))
        app.append_step_event(self.data_dir, step("fake-step-002", action="update", revision=1,
                                                  changes={"status": "blocked"}, step_id=sid))
        app.append_step_event(self.data_dir, step("fake-step-003", action="update", revision=1,
                                                  changes={"status": "doing"}, step_id=sid))
        state = self.task()
        self.assertEqual(state["status"], "todo")
        self.assertEqual(state["status_source"], "task")

    def test_google_drive_links_validate_and_append_only(self):
        url = "https://drive.google.com/file/d/SYNTHETIC_FILE_ABC/view?usp=sharing"
        links = [{"title": "虚构参考文档", "url": url}]
        self.assertEqual(app.validate_document_links(links), links)
        app.append_event(self.data_dir, evt("fake-doc-link-001", "update", 1,
                                            {"document_links": links}))
        self.assertEqual(self.task()["document_links"], links)
        for invalid in [
            "javascript:alert(1)", "http://drive.google.com/file/d/abc/view",
            "https://drive.google.com.evil.example/file/d/abc/view",
            "https://docs.google.com.evil.example/document/d/abc/edit",
            "https://drive.google.com@evil.example/file/d/abc/view",
            "https://drive.google.com/any/random/path",
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                app.validate_document_links([{"title": "x", "url": invalid}])

    def test_only_user_can_trash_or_purge(self):
        for action, changes in [("trash", {"trashed_at": "2026-11-02T00:00:00Z"}),
                                ("purge", {"purged_at": "2026-11-02T00:00:00Z"})]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                app.validate_event(evt("evil-actor-001", action=action, revision=1,
                                       changes=changes, actor="chatgpt"))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        app.append_event(self.data_dir, evt("fake-create-001"))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, payload=None):
        if payload is None:
            request = Request(self.base + path)
        else:
            request = Request(self.base + path, method="POST",
                              data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=3) as result:
                return result.status, json.load(result)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_document_link_post_and_stale_revision(self):
        path = "/api/tasks/TASK-FAKE-001/documents"
        links = [{"title": "虚构资料",
                  "url": "https://docs.google.com/document/d/FAKE_DOC123/edit"}]
        code, body = self.request(path, {"revision": 1, "links": links})
        self.assertEqual(code, 200)
        self.assertTrue(body["saved"])
        self.assertEqual(self.request("/api/tasks")[1]["tasks"][0]["document_links"], links)
        self.assertEqual(self.request(path, {"revision": 1, "links": []})[0], 409)
        self.assertEqual(self.request(path, {"revision": 2, "links": [
            {"title": "evil", "url": "javascript:alert(1)"}]})[0], 400)

    def test_trash_restore_and_purge_confirmation(self):
        path = "/api/tasks/TASK-FAKE-001/"
        code, body = self.request(path + "trash", {"revision": 1})
        self.assertEqual(code, 200, body)
        self.assertEqual(self.request("/api/tasks")[1]["tasks"], [])
        trash = self.request("/api/trash")[1]
        self.assertEqual(len(trash["tasks"]), 1)
        self.assertEqual(self.request(path + "purge", {"revision": 2})[0], 400)
        self.assertEqual(self.request(path + "restore", {"revision": 1})[0], 409)
        self.assertEqual(self.request(path + "restore", {"revision": 2})[0], 200)
        self.assertEqual(len(self.request("/api/tasks")[1]["tasks"]), 1)
        self.assertEqual(self.request(path + "trash", {"revision": 3})[0], 200)
        self.assertEqual(self.request(path + "purge", {"revision": 4,
                                                         "confirmed_purge": True})[0], 200)
        self.assertEqual(self.request("/api/trash")[1]["tasks"], [])

    def test_retention_setting_and_invalid_policy(self):
        self.assertEqual(self.request("/api/trash")[1]["retention_days"], 30)
        self.assertEqual(self.request("/api/trash/settings", {"retention_days": 5})[0], 400)
        self.assertEqual(self.request("/api/trash/settings", {"retention_days": 90})[0], 200)
        self.assertEqual(self.request("/api/trash")[1]["retention_days"], 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
