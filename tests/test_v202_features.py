"""V2.0.2 lifecycle, derived statuses and Google Drive links with fake data only."""
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

    def test_imported_purge_marker_hides_without_erasing_unconfirmed_local_files(self):
        # A synced purge marker is not an authenticated local request to erase
        # old event bytes. Preserve files pending explicit local cleanup while
        # hiding the task from both active and trash API results.
        app.append_event(self.data_dir, evt("remote-purge-marker-001", "purge", 1,
                                            {"purged_at": "2026-11-02T00:00:00Z"}))
        before = sorted((self.data_dir / "events").glob("*.json"))
        self.assertEqual(len(before), 2)
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"], [])
        app.expire_trashed_tasks(self.data_dir)
        self.assertEqual(sorted((self.data_dir / "events").glob("*.json")), before)

    def test_two_device_delayed_sync_cannot_resurrect_permanently_deleted_task(self):
        """Second machine receives the tombstone after stale files, then stale files again."""
        import shutil
        with tempfile.TemporaryDirectory() as other_home:
            remote = Path(other_home)
            for folder in ("events", "step_events"):
                source = self.data_dir / folder
                if source.is_dir():
                    shutil.copytree(source, remote / folder)
            # Two devices initially see the same task and step.
            app.append_step_event(self.data_dir, step("fake-step-001"))
            (remote / "step_events").mkdir(exist_ok=True)
            for old in (self.data_dir / "step_events").glob("*.json"):
                shutil.copy2(old, remote / "step_events" / old.name)
            original_files = {
                folder: [(file.name, file.read_bytes())
                         for file in (remote / folder).glob("*.json")]
                for folder in ("events", "step_events")
            }
            app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                                {"trashed_at": "2026-10-01T01:00:00Z"}))
            for trash in (self.data_dir / "events").glob("*.json"):
                if json.loads(trash.read_text("utf-8"))["action"] == "trash":
                    shutil.copy2(trash, remote / "events" / trash.name)
            self.assertEqual(app.read_workspace(remote)["tasks"], [])
            app.append_task_lifecycle(self.data_dir, self.task(), "purge")
            for tombstone in (self.data_dir / "events").glob("*.json"):
                self.assertEqual(json.loads(tombstone.read_text("utf-8"))["action"], "purge")
                shutil.copy2(tombstone, remote / "events" / tombstone.name)
            self.assertEqual(app.read_workspace(remote, include_trashed=True)["tasks"], [])
            # Remote machine has not yet propagated old source-file deletion.
            self.assertGreater(len(list((remote / "events").glob("*.json"))), 1)
            app.expire_trashed_tasks(remote)
            # Imported tombstones hide tasks, but may not silently erase the
            # second device's local files without local authorization.
            self.assertGreater(len(list((remote / "events").glob("*.json"))), 1)
            self.assertGreater(len(list((remote / "step_events").glob("*.json"))), 0)
            # A stale offline machine uploads the original files again.
            for folder, files in original_files.items():
                for name, payload in files:
                    (remote / folder / name).write_bytes(payload)
            # Even before local physical cleanup, tombstones prevent resurrection.
            self.assertEqual(app.read_workspace(remote)["tasks"], [])
            app.expire_trashed_tasks(remote)
            self.assertGreater(len(list((remote / "events").glob("*.json"))), 1)
            self.assertGreater(len(list((remote / "step_events").glob("*.json"))), 0)
            self.assertEqual(app.read_workspace(remote, include_trashed=True)["tasks"], [])

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

    def test_concurrent_retention_setting_disables_destructive_auto_purge(self):
        app.append_event(self.data_dir, evt("fake-trash-001", "trash", 1,
                                            {"trashed_at": "2020-01-01T01:00:00Z"}))
        for suffix, days in (("one", 7), ("two", 90)):
            setting = {"version": 1, "event_id": "settings-concurrent-" + suffix,
                       "key": "trash_retention_days", "days": days,
                       "timestamp": "2026-11-02T01:00:00Z"}
            app._append_json_event(self.data_dir, setting, "settings_events")
        days, warnings = app.read_trash_retention(self.data_dir)
        self.assertEqual(days, 0)
        self.assertTrue(any("conflict" in text for text in warnings))
        app.expire_trashed_tasks(self.data_dir)
        self.assertEqual(len(app.read_workspace(self.data_dir, include_trashed=True)["tasks"]), 1)

    def test_invalid_lifecycle_cannot_be_used_as_purge_marker(self):
        event = evt("fake-purge-invalid", "purge", 1,
                    {"purged_at": "2026-11-02T00:00:00Z"}, actor="chatgpt")
        folder = self.data_dir / "events"
        (folder / "evt_fake-purge-invalid.json").write_text(
            json.dumps(event), encoding="utf-8")
        self.assertEqual(len(app.read_workspace(self.data_dir)["tasks"]), 1)

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
