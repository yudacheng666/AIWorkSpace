"""Explicit parent/child and step status rollup regression using synthetic events only."""
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


def task_event(id, task_id, action="create", revision=0, changes=None, **extras):
    if changes is None:
        changes = {"title": "虚构任务 " + task_id, "status": "todo"}
    return {"version": 1, "event_id": id, "task_id": task_id, "action": action,
            "actor": "user", "timestamp": "2026-11-02T08:00:00Z",
            "base_revision": revision, "changes": changes, **extras}


def step_event(id, task_id, step_id, action="create", revision=0, changes=None,
               **extras):
    if changes is None:
        changes = {"title": "虚构执行步骤", "position": 1}
    return {"version": 1, "event_id": id, "task_id": task_id, "step_id": step_id,
            "action": action, "actor": "user", "timestamp": "2026-11-02T08:00:00Z",
            "base_revision": revision, "changes": changes, **extras}


class ParentStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.parent = "TASK-SYNTHETIC-PARENT"
        self.child = "TASK-SYNTHETIC-CHILD"
        self.grandchild = "TASK-SYNTHETIC-GRANDCHILD"
        app.append_event(self.dir, task_event("synthetic-root-001", self.parent))
        app.append_event(self.dir, task_event("synthetic-child-001", self.child, changes={
            "title": "虚构子任务", "status": "todo", "parent_task_id": self.parent}))

    def read(self):
        return {x["task_id"]: x for x in app.read_workspace(self.dir)["tasks"]}

    def update(self, id, task_id, rev, changes, **kwargs):
        app.append_event(self.dir, task_event(id, task_id, "update", rev, changes, **kwargs))

    def test_manual_child_status_drives_parent_without_writing_parent_event(self):
        self.assertEqual(self.read()[self.parent]["status"], "todo")
        self.update("synthetic-child-doing", self.child, 1, {"status": "doing"})
        tasks = self.read()
        self.assertEqual(tasks[self.parent]["status"], "doing")
        self.assertEqual(tasks[self.parent]["manual_status"], "todo")
        self.assertEqual(tasks[self.parent]["status_source"], "children")
        self.assertEqual(tasks[self.parent]["child_task_ids"], [self.child])
        self.assertEqual(tasks[self.child]["parent_title"], "虚构任务 " + self.parent)
        self.assertEqual(len(list((self.dir / "events").glob("*.json"))), 3)
        self.update("synthetic-child-blocked", self.child, 2, {"status": "blocked"})
        self.assertEqual(self.read()[self.parent]["status"], "blocked")
        self.update("synthetic-child-todo", self.child, 3, {"status": "todo"})
        self.assertEqual(self.read()[self.parent]["status"], "todo")
        self.update("synthetic-child-done", self.child, 4, {"status": "done"},
                    confirmed_done=True)
        tasks = self.read()
        self.assertEqual(tasks[self.parent]["status"], "doing")
        self.assertTrue(tasks[self.parent]["step_completion_pending"])
        self.update("synthetic-parent-done", self.parent, 1, {"status": "done"},
                    confirmed_done=True)
        self.assertEqual(self.read()[self.parent]["status"], "done")
        self.update("synthetic-child-reopen", self.child, 5, {"status": "doing"})
        self.assertEqual(self.read()[self.parent]["status"], "done",
                         "completed parent stays done until a user reopens it")

    def test_nested_children_steps_and_priority(self):
        self.update("synthetic-grand-001", self.child, 1, {"title": "二级任务"})
        app.append_event(self.dir, task_event(
            "synthetic-grand-create-001", self.grandchild, changes={
                "title": "虚构孙任务", "status": "todo", "parent_task_id": self.child}))
        app.append_step_event(self.dir, step_event(
            "synthetic-step-create-001", self.parent, "STEP-" + "A" * 32))
        app.append_step_event(self.dir, step_event(
            "synthetic-step-doing-001", self.parent, "STEP-" + "A" * 32, "update",
            1, {"status": "doing"}))
        self.assertEqual(self.read()[self.parent]["status"], "doing")
        self.assertEqual(self.read()[self.parent]["status_source"], "steps_and_children")
        self.update("synthetic-grand-blocked", self.grandchild, 1, {"status": "blocked"})
        self.assertEqual(self.read()[self.parent]["status"], "blocked",
                         "grandchild blocked status propagates recursively")
        self.update("synthetic-grand-done", self.grandchild, 2, {"status": "done"},
                    confirmed_done=True)
        self.assertEqual(self.read()[self.parent]["status"], "doing")

    def test_conflicted_child_freezes_parent_and_unrelated_task_stays_independent(self):
        self.update("synthetic-child-dupe-A", self.child, 1, {"status": "doing"})
        self.update("synthetic-child-dupe-B", self.child, 1, {"status": "blocked"})
        parent = self.read()[self.parent]
        self.assertEqual(parent["status"], "todo")
        self.assertEqual(parent["status_source"], "task")
        self.assertTrue(parent["status_rollup_incomplete"])
        self.assertEqual(self.read()[self.child]["conflict"], True)
        independent = "TASK-UNRELATED-SYNTHETIC"
        app.append_event(self.dir, task_event("synthetic-independent-001", independent))
        self.assertEqual(self.read()[independent]["status"], "todo")

    def test_cycle_from_external_sync_freezes_without_recursion(self):
        self.update("synthetic-parent-link-child", self.parent, 1,
                    {"parent_task_id": self.child})
        tasks = self.read()
        self.assertTrue(tasks[self.parent]["parent_cycle"])
        self.assertTrue(tasks[self.child]["parent_cycle"])
        self.assertEqual(tasks[self.parent]["status"], "todo")
        self.assertTrue(tasks[self.parent]["status_rollup_incomplete"])

    def test_deleted_child_does_not_drive_parent(self):
        self.update("synthetic-child-active", self.child, 1, {"status": "doing"})
        self.assertEqual(self.read()[self.parent]["status"], "doing")
        app.append_event(self.dir, task_event(
            "synthetic-child-trash", self.child, "trash", 2,
            {"trashed_at": "2026-11-02T09:00:00Z"}))
        self.assertEqual(self.read()[self.parent]["status"], "todo")
        self.assertEqual(self.read()[self.parent]["child_task_ids"], [])

    def test_invalid_self_reference_and_missing_links_rejected(self):
        with self.assertRaises(ValueError):
            app.validate_event(task_event(
                "synthetic-self-001", self.parent, "update", 1,
                {"parent_task_id": self.parent}))
        with self.assertRaisesRegex(ValueError, "missing"):
            app.validate_parent_assignment(list(self.read().values()), self.child,
                                           "TASK-SYNTHETIC-MISSING")
        with self.assertRaisesRegex(ValueError, "cycle"):
            app.validate_parent_assignment(list(self.read().values()),
                                           self.parent, self.child)


class ParentApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.parent = "TASK-SYNTHETIC-PARENT"
        app.append_event(self.dir, task_event("synthetic-api-root", self.parent))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def request(self, path, payload=None):
        req = Request(self.base + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"} if payload is not None else {})
        try:
            with urlopen(req, timeout=5) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_link_child_update_and_preserve_manual_status_on_title_edit(self):
        code, new = self.request("/api/tasks", {
            "title": "虚构新子任务", "parent_task_id": self.parent})
        self.assertEqual(code, 201, new)
        child = new["task_id"]
        status, state = self.request("/api/tasks")
        self.assertEqual(status, 200)
        tasks = {item["task_id"]: item for item in state["tasks"]}
        self.assertEqual(tasks[child]["parent_task_id"], self.parent)
        self.assertEqual(tasks[self.parent]["child_task_ids"], [child])
        update = "/api/tasks/" + child + "/update"
        self.assertEqual(self.request(update, {
            "title": "虚构新子任务", "revision": 1, "status": "doing"})[0], 200)
        tasks = {item["task_id"]: item for item in self.request("/api/tasks")[1]["tasks"]}
        self.assertEqual(tasks[self.parent]["status"], "doing")
        self.assertEqual(tasks[self.parent]["manual_status"], "todo")
        url = "/api/tasks/" + self.parent + "/update"
        self.assertEqual(self.request(url, {
            "title": "仅更改父任务标题", "revision": 1})[0], 200)
        tasks = {item["task_id"]: item for item in self.request("/api/tasks")[1]["tasks"]}
        self.assertEqual(tasks[self.parent]["manual_status"], "todo")
        self.assertEqual(tasks[self.parent]["status"], "doing")
        self.assertEqual(tasks[self.parent]["revision"], 2)
        self.assertEqual(self.request(url, {
            "title": "仅更改父任务标题", "revision": 1})[0], 409)
        self.assertEqual(self.request("/api/tasks/" + child + "/update", {
            "title": "虚构新子任务", "revision": 2, "parent_task_id": child})[0], 400)
        self.assertEqual(self.request(url, {
            "title": "仅更改父任务标题", "revision": 2,
            "parent_task_id": child})[0], 400)
        self.assertEqual(self.request(url, {
            "title": "仅更改父任务标题", "revision": 2,
            "parent_task_id": "TASK-NONEXISTENT"})[0], 400)


if __name__ == "__main__":
    unittest.main()
