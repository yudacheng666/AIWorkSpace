"""Synthetic, isolated step deletion and step-scoped Google Drive link tests."""
import json
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


def record(event_id, task_id, step_id=None, action="create", revision=0, changes=None,
           actor="user", **extras):
    if changes is None:
        changes = {"title": "虚构任务", "status": "todo"} if step_id is None else {
            "title": "虚构执行步骤", "position": 1}
    value = {"version": 1, "event_id": event_id, "task_id": task_id,
             "action": action, "actor": actor, "timestamp": "2026-11-03T04:00:00Z",
             "base_revision": revision, "changes": changes, **extras}
    if step_id:
        value["step_id"] = step_id
    return value


class StepDeleteAndDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.tid = "TASK-SYNTHETIC-STEP"
        app.append_event(self.data, record("synth-task-create-01", self.tid))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.data))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def call(self, endpoint, payload=None):
        request = Request(self.base + endpoint,
                          data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                          headers={"Content-Type": "application/json"} if payload is not None else {})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def task(self):
        return self.call("/api/tasks")[1]["tasks"][0]

    def step(self, title="虚构执行步骤"):
        status, result = self.call("/api/tasks/" + self.tid + "/steps", {"title": title})
        self.assertEqual(status, 201, result)
        return result["step_id"]

    def step_path(self, sid, suffix):
        return "/api/tasks/" + self.tid + "/steps/" + sid + "/" + suffix

    def link(self, suffix="ONE"):
        return {"title": "虚构云端资料" + suffix,
                "url": "https://docs.google.com/document/d/SYNTHETIC_" + suffix + "/edit"}

    def test_new_links_are_independent_per_step_and_revision_guarded(self):
        a, b = self.step("步骤甲"), self.step("步骤乙")
        link = self.link()
        url = self.step_path(a, "documents")
        self.assertEqual(self.call(url, {"revision": 1, "links": [link]})[0], 200)
        self.assertEqual(self.call(url, {"revision": 1, "links": []})[0], 409)
        self.assertEqual(self.call(url, {"revision": 2, "links": [link]})[1]["saved"], False)
        steps = {step["step_id"]: step for step in self.task()["steps"]}
        self.assertEqual(steps[a]["document_links"], [link])
        self.assertEqual(steps[a]["revision"], 2)
        self.assertEqual(steps[b]["document_links"], [])
        self.assertEqual(self.task()["document_links"], [])
        self.assertEqual(self.task()["revision"], 1,
                         "step links must not mutate the parent task revision")
        self.assertEqual(self.call(self.step_path(b, "documents"), {
            "revision": 1, "links": [link]})[0], 200,
            "same file may be linked independently to multiple steps")
        self.assertEqual(self.call(url, {"revision": 2, "links": []})[0], 200)
        self.assertEqual(steps[a]["document_links"], [link], "old snapshot is immutable")
        self.assertEqual(next(s for s in self.task()["steps"] if s["step_id"] == a)["document_links"], [])

    def test_invalid_links_and_duplicate_links_cannot_be_saved(self):
        sid = self.step()
        endpoint = self.step_path(sid, "documents")
        for links in [
            [{"title": "bad", "url": "javascript:alert(1)"}],
            [{"title": "bad", "url": "https://drive.google.com.evil.test/file/d/x/view"}],
            [self.link(), self.link()],
            [{"title": "empty", "url": "http://drive.google.com/file/d/abc/view"}],
            [self.link(str(i)) for i in range(21)],
        ]:
            with self.subTest(links=links):
                self.assertEqual(self.call(endpoint, {"revision": 1, "links": links})[0], 400)
        self.assertEqual(self.task()["steps"][0]["revision"], 1)

    def test_delete_requires_confirmation_and_exact_revision(self):
        sid = self.step()
        endpoint = self.step_path(sid, "delete")
        for body in [{"revision": 1}, {"revision": 1, "confirmed_delete": False},
                     {"revision": True, "confirmed_delete": True},
                     {"revision": 1, "confirmed_delete": True, "extra": 1}]:
            self.assertEqual(self.call(endpoint, body)[0], 400)
        self.assertEqual(self.call(endpoint, {"revision": 2, "confirmed_delete": True})[0], 409)
        self.assertEqual(self.call(endpoint, {"revision": 1, "confirmed_delete": True})[0], 200)
        self.assertEqual(self.task()["steps"], [])
        self.assertEqual(self.task()["revision"], 1)
        self.assertEqual(self.task()["status"], "todo")
        self.assertEqual(self.call(endpoint, {"revision": 1, "confirmed_delete": True})[0], 404)
        self.assertEqual(self.call(self.step_path(sid, "documents"), {
            "revision": 2, "links": [self.link()]})[0], 404)
        events = [json.loads(path.read_text("utf-8"))
                  for path in (self.data / "step_events").glob("*.json")]
        self.assertEqual(len(events), 2, "append-only delete must keep original step event")
        self.assertEqual(sum(e["action"] == "delete" for e in events), 1)
        deleted = next(e for e in events if e["action"] == "delete")
        self.assertTrue(deleted["confirmed_delete"])

    def test_delete_preserves_other_steps_order_and_rollup(self):
        first, second = self.step("虚构受阻步骤"), self.step("虚构继续步骤")
        self.assertEqual(self.call(self.step_path(first, "update"), {
            "revision": 1, "status": "blocked"})[0], 200)
        self.assertEqual(self.task()["status"], "blocked")
        self.assertEqual(self.call("/api/tasks/" + self.tid + "/steps/reorder", {
            "revision": 0, "step_ids": [second, first]})[0], 200)
        self.assertEqual(self.call(self.step_path(first, "delete"), {
            "revision": 2, "confirmed_delete": True})[0], 200)
        task = self.task()
        self.assertEqual([step["step_id"] for step in task["steps"]], [second])
        self.assertEqual([step["position"] for step in task["steps"]], [1])
        self.assertFalse(task["step_order_incomplete"],
                         "the known deleted step in a historical order isn't an unsynced missing step")
        self.assertFalse(task["step_order_conflict"])
        self.assertEqual(task["step_order_revision"], 1)
        self.assertEqual(task["status"], "todo")
        self.assertEqual(self.call(self.step_path(second, "update"), {
            "revision": 1, "status": "doing"})[0], 200)
        self.assertEqual(self.task()["status"], "doing")

    def test_deleted_step_link_remains_in_historical_events(self):
        sid = self.step()
        self.assertEqual(self.call(self.step_path(sid, "documents"), {
            "revision": 1, "links": [self.link()]})[0], 200)
        self.assertEqual(self.call(self.step_path(sid, "delete"), {
            "revision": 2, "confirmed_delete": True})[0], 200)
        self.assertEqual(self.task()["steps"], [])
        raw = [json.loads(p.read_text("utf-8"))
               for p in (self.data / "step_events").glob("*.json")]
        self.assertTrue(any(event["changes"].get("document_links") == [self.link()]
                            for event in raw))
        self.assertTrue(any(event["action"] == "delete" for event in raw))
        self.assertEqual(len(raw), 3)

    def test_legacy_task_links_preserved_read_only(self):
        old = self.link("LEGACY")
        app.append_event(self.data, record("synthetic-legacy-doc", self.tid,
                                           action="update", revision=1,
                                           changes={"document_links": [old]}))
        self.assertEqual(self.task()["document_links"], [old])
        before = list((self.data / "events").glob("*.json"))
        self.assertEqual(self.call("/api/tasks/" + self.tid + "/documents", {
            "revision": 2, "links": []})[0], 410)
        self.assertEqual(self.task()["document_links"], [old])
        self.assertEqual(len(list((self.data / "events").glob("*.json"))), len(before))
        sid = self.step()
        self.assertEqual(self.call(self.step_path(sid, "documents"), {
            "revision": 1, "links": [old]})[0], 200)
        self.assertEqual(self.task()["document_links"], [old],
                         "new step association does not silently remove legacy task link")

    def test_conflicting_step_document_edits_block_delete(self):
        sid = self.step()
        app.append_step_event(self.data, record("synthetic-fork-doc-A", self.tid, sid,
                                                "update", 1,
                                                {"document_links": [self.link("A")]}))
        app.append_step_event(self.data, record("synthetic-fork-doc-B", self.tid, sid,
                                                "update", 1,
                                                {"document_links": [self.link("B")]}))
        task = self.task()
        self.assertTrue(task["steps"][0]["conflict"])
        self.assertEqual(self.call(self.step_path(sid, "delete"), {
            "revision": 1, "confirmed_delete": True})[0], 409)
        self.assertEqual(self.call(self.step_path(sid, "documents"), {
            "revision": 1, "links": []})[0], 409)

    def test_invalid_remote_delete_event_cannot_override_existing_data(self):
        sid = self.step()
        event = record("synth-invalid-delete", self.tid, sid,
                       "delete", 1, {"deleted_at": "2026-11-03T10:00:00Z"})
        for item in [event, {**event, "confirmed_delete": True, "actor": "chatgpt"},
                     {**event, "confirmed_delete": True,
                      "changes": {"deleted_at": "not-a-timestamp"}}]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                app.validate_step_event(item)
        self.assertEqual(self.task()["steps"][0]["step_id"], sid)

    def test_delayed_duplicate_create_does_not_resurrect_tombstone(self):
        sid = self.step()
        self.assertEqual(self.call(self.step_path(sid, "delete"), {
            "revision": 1, "confirmed_delete": True})[0], 200)
        original = next(json.loads(p.read_text("utf-8")) for p in
                        (self.data / "step_events").glob("*.json")
                        if json.loads(p.read_text("utf-8"))["action"] == "create")
        (self.data / "step_events" / ("evt_duplicate_" + uuid.uuid4().hex + ".json")).write_text(
            json.dumps(original), encoding="utf-8")
        self.assertEqual(self.task()["steps"], [])
        self.assertFalse(self.task()["step_order_incomplete"])


if __name__ == "__main__":
    unittest.main()
