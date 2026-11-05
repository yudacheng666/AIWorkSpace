"""Task -> factual work-record conversion tests; synthetic data only."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app

TASK = "TASK-SYNTHETIC-RECORD-CONVERSION"
PROJECT = "PROJECT-" + "D" * 32
RECORD = "RECORD-" + "E" * 32
STAMP = "2026-11-06T01:00:00Z"


def task_event(action, revision, changes, eid):
    return {"version": 1, "event_id": eid, "task_id": TASK,
            "action": action, "actor": "user", "timestamp": STAMP,
            "base_revision": revision, "changes": changes}


def conversion(task, record_id=RECORD, event_id="task-convert-0001"):
    return {
        "version": 1, "event_id": event_id, "action": "task_to_record",
        "actor": "user", "timestamp": STAMP, "confirmed_move": True,
        "source": {"task_id": task["task_id"], "revision": task["revision"],
                   "snapshot_sha256": app.task_record_source_hash(task)},
        "target": {"record_id": record_id, "content": "与虚构供应商讨论需求",
                   "occurred_on": "2026-11-04", "project_id": PROJECT,
                   "outcome": "收到确认", "duration_minutes": 35,
                   "evidence_links": []}
    }


class TaskRecordConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        app.append_project_event(self.data_dir, {
            "version": 1, "event_id": "task-record-project-0001",
            "project_id": PROJECT, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"name": "虚构案例项目"}
        })
        app.append_event(self.data_dir, task_event("create", 0, {
            "title": "误建成待办的历史沟通", "status": "todo",
            "project_id": PROJECT
        }, "task-record-create-0001"))
        self.original_bytes = {
            f.name: f.read_bytes() for f in (self.data_dir / "events").glob("*.json")
        }

    def tearDown(self):
        self.temp.cleanup()

    def current_task(self):
        return app.read_workspace(self.data_dir)["tasks"][0]

    def test_strict_event_schema_requires_user_confirmation_and_true_dates(self):
        original = conversion(self.current_task())
        self.assertEqual(app.validate_task_record_conversion(original), original)
        invalid = [
            {**original, "actor": "chatgpt"},
            {**original, "confirmed_move": False},
            {**original, "action": "copy_to_record"},
            {**original, "timestamp": "2026-11-06"},
            {**original, "unexpected": True},
            {**original, "source": {**original["source"], "revision": True}},
            {**original, "source": {**original["source"], "snapshot_sha256": "bad"}},
            {**original, "target": {**original["target"], "occurred_on": "2026-02-29"}},
            {**original, "target": {**original["target"], "status": "done"}},
            {**original, "target": {**original["target"], "content": " "}},
            {**original, "target": {**original["target"], "duration_minutes": 0}},
            {**original, "target": {**original["target"], "evidence_links": [
                {"title": "unsafe", "url": "http://fake.example"}]}},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                app.validate_task_record_conversion(item)

    def test_one_ledger_hides_old_task_preserves_original_bytes_and_can_edit_record(self):
        task = self.current_task()
        created = conversion(task)
        app.append_task_record_conversion(self.data_dir, created)
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"], [])
        state = app.read_work_records(self.data_dir)
        self.assertEqual(state["warnings"], [])
        self.assertEqual(len(state["records"]), 1)
        self.assertEqual(state["records"][0]["record_id"], RECORD)
        self.assertEqual(state["records"][0]["source_task_id"], TASK)
        self.assertEqual(state["records"][0]["revision"], 1)
        self.assertEqual(state["records"][0]["duration_minutes"], 35)
        self.assertEqual(app.read_workspace(self.data_dir,
            hide_work_record_sources=False)["tasks"][0]["task_id"], TASK)
        app.append_work_record_event(self.data_dir, {
            "version": 1, "event_id": "task-convert-record-update-0001",
            "record_id": RECORD, "action": "update", "actor": "user",
            "timestamp": STAMP, "base_revision": 1,
            "changes": {"outcome": "再次人工核对"}
        })
        record = app.read_work_records(self.data_dir)["records"][0]
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["outcome"], "再次人工核对")
        self.assertEqual(self.original_bytes, {
            f.name: f.read_bytes() for f in (self.data_dir / "events").glob("*.json")
        })
        self.assertEqual(len(list((self.data_dir / app.TASK_RECORD_CONVERSION_DIR)
                                  .glob("*.json"))), 1)

    def test_late_source_edit_freezes_conversion_and_unhides_source(self):
        app.append_task_record_conversion(self.data_dir, conversion(self.current_task()))
        app.append_event(self.data_dir, task_event("update", 1, {
            "title": "后续设备上发生编辑"
        }, "task-record-late-edit-0001"))
        visible = app.read_workspace(self.data_dir)
        self.assertEqual(visible["tasks"][0]["title"], "后续设备上发生编辑")
        self.assertTrue(any("conversion source changed" in text
                            for text in visible["warnings"]))
        self.assertEqual(app.read_work_records(self.data_dir)["records"], [])

    def test_duplicate_and_corrupt_conversion_cannot_hide_source(self):
        app.append_task_record_conversion(self.data_dir, conversion(self.current_task()))
        app.append_task_record_conversion(self.data_dir, conversion(
            self.current_task(), record_id="RECORD-" + "F" * 32,
            event_id="task-convert-0002"))
        self.assertEqual(len(app.read_workspace(self.data_dir)["tasks"]), 1)
        self.assertEqual(app.read_work_records(self.data_dir)["records"], [])
        self.assertTrue(app.read_workspace(self.data_dir)["warnings"])
        directory = self.data_dir / app.TASK_RECORD_CONVERSION_DIR
        for f in directory.glob("evt_*.json"):
            f.unlink()
        app.append_task_record_conversion(self.data_dir, conversion(self.current_task()))
        (directory / "corrupt.json").write_text('{"broken":', encoding="utf-8")
        self.assertEqual(len(app.read_workspace(self.data_dir)["tasks"]), 1)
        self.assertEqual(app.read_work_records(self.data_dir)["records"], [])

    def test_record_id_collision_does_not_hide_original_task(self):
        app.append_work_record_event(self.data_dir, {
            "version": 1, "event_id": "task-record-creation-0001",
            "record_id": RECORD, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"content": "已有另一条记录", "occurred_on": "2026-11-01"}
        })
        app.append_task_record_conversion(self.data_dir, conversion(self.current_task()))
        self.assertEqual(len(app.read_workspace(self.data_dir)["tasks"]), 1)
        state = app.read_work_records(self.data_dir)
        self.assertEqual(len(state["records"]), 1)
        self.assertNotIn("source_task_id", state["records"][0])
        self.assertTrue(any("record ID collision" in text for text in state["warnings"]))

    def test_standalone_rule_rejects_steps_and_recurrence(self):
        task = self.current_task()
        self.assertTrue(app.task_record_source_allowed(task))
        for change in ({"steps": [{"step_id": "STEP-" + "A" * 32}]},
                       {"all_child_task_ids": [TASK + "-CHILD"]},
                       {"parent_task_id": "TASK-PARENT"},
                       {"recurrence": {"unit": "daily", "interval": 1,
                                       "start_date": "2026-11-01", "enabled": True}},
                       {"conflict": True},
                       {"trashed_at": STAMP},
                       {"source_work_record": {"record_id": RECORD, "revision": 1}}):
            with self.subTest(change=change):
                self.assertFalse(app.task_record_source_allowed({**task, **change}))


class TaskRecordConversionHTTPTests(TaskRecordConversionTests):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          app.handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        super().tearDown()

    def request(self, method, path, payload=None, headers=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base + path, data=body, method=method,
                          headers={"Content-Type": "application/json",
                                   **(headers or {})})
        try:
            with urlopen(request, timeout=5) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_http_user_confirmation_revision_and_single_file(self):
        path = "/api/work-archive/tasks/" + TASK + "/convert-to-record"
        body = {"revision": 1, "content": "整理已处理的虚构工作",
                "occurred_on": "2026-11-03", "outcome": "已发确认邮件",
                "duration_minutes": None, "confirmed_move": True}
        self.assertEqual(self.request("POST", path, {**body, "confirmed_move": False})[0], 400)
        self.assertEqual(self.request("POST", path, {**body, "revision": 2})[0], 409)
        self.assertEqual(self.request("POST", path, {**body, "status": "done"})[0], 400)
        self.assertEqual(self.request("POST", path, {**body, "occurred_on": "2026-02-29"})[0], 400)
        self.assertEqual(self.request("POST", path, body,
            {"Origin": "https://outside.example"})[0], 403)
        self.assertEqual(len(list((self.data_dir / app.TASK_RECORD_CONVERSION_DIR)
                                  .glob("*.json"))), 0)
        status, result = self.request("POST", path, body)
        self.assertEqual(status, 201, result)
        self.assertTrue(result["record_id"].startswith("RECORD-"))
        self.assertEqual(self.request("POST", path, body)[0], 409)
        _, tasks = self.request("GET", "/api/tasks")
        self.assertEqual(tasks["tasks"], [])
        _, records = self.request("GET", "/api/work-records")
        self.assertEqual(records["records"][0]["source_task_id"], TASK)
        self.assertEqual(records["records"][0]["content"], body["content"])
        self.assertEqual(self.original_bytes, {
            f.name: f.read_bytes() for f in (self.data_dir / "events").glob("*.json")
        })


if __name__ == "__main__":
    unittest.main()
