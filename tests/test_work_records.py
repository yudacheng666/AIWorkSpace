"""Work record persistence and HTTP tests, using synthetic temporary data only."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app


RECORD = "RECORD-" + "A" * 32
TASK = "TASK-WORK-TEST-001"
PROJECT = "PROJECT-" + "B" * 32


def work_event(eid="work-create-0001", action="create", revision=0, changes=None,
               record_id=RECORD):
    if changes is None:
        changes = {"content": "上午沟通交期，下午问题解决", "occurred_on": "2026-10-31"}
    return {"version": 1, "event_id": eid, "record_id": record_id,
            "action": action, "actor": "user",
            "timestamp": "2026-11-05T03:25:00Z",
            "base_revision": revision, "changes": changes}


def task_event(eid, action, revision, changes, *, done=False):
    event = {"version": 1, "event_id": eid, "task_id": TASK, "action": action,
             "actor": "user", "timestamp": "2026-11-05T07:00:00Z",
             "base_revision": revision, "changes": changes}
    if done:
        event["confirmed_done"] = True
    return event


class WorkRecordValidationTests(unittest.TestCase):
    def test_fact_not_task_and_bad_fields_are_rejected(self):
        self.assertEqual(app.validate_work_record_event(work_event()), work_event())
        for changes in (
            {"content": " ", "occurred_on": "2026-11-05"},
            {"content": "事实", "occurred_on": "2026-02-29"},
            {"content": "事实", "occurred_on": "2026-11-05", "status": "done"},
            {"content": "事实", "occurred_on": "2026-11-05", "duration_minutes": True},
            {"content": "事实", "occurred_on": "2026-11-05", "duration_minutes": -1},
            {"content": "事实", "occurred_on": "2026-11-05", "project_id": "TASK-FAKE"},
            {"content": "x" * 4001, "occurred_on": "2026-11-05"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                app.validate_work_record_event(work_event(changes=changes))
        for value in (
            {**work_event(), "actor": "machine"},
            {**work_event(), "timestamp": "2026-11-05"},
            {**work_event(), "status": "done"},
            {**work_event(), "confirmed_done": True},
            {**work_event(), "unexpected": "not part of the work-record envelope"},
            work_event(action="update", revision=0),
            work_event(action="create", revision=2),
            {**work_event(), "record_id": "RECORD-../../"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.validate_work_record_event(value)

    def test_output_id_uses_capture_day_not_edited_work_day(self):
        self.assertEqual(app.work_record_display_id(RECORD, "2026-11-05T03:25:00Z"),
                         "R-261105-AAAAAAAAAAAA")

    def test_record_type_is_optional_for_legacy_and_rejects_unknown_values(self):
        self.assertEqual(app.validate_work_record_event(work_event()), work_event())
        for value in ("unknown", None, [], {}):
            with self.subTest(record_type=value), self.assertRaises(ValueError):
                app.validate_work_record_event(work_event(changes={
                    "content": "评估是否转卖零件", "occurred_on": "2026-11-11",
                    "record_type": value}))


class WorkRecordReducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_legacy_data_and_append_only_updates(self):
        self.assertEqual(app.read_work_records(self.data_dir),
                         {"records": [], "warnings": []})
        app.append_event(self.data_dir, task_event("old-create-0001", "create", 0,
                          {"title": "旧任务", "status": "todo"}))
        legacy_bytes = {p.name: p.read_bytes() for p in (self.data_dir / "events").glob("*.json")}
        app.append_work_record_event(self.data_dir, work_event())
        state = app.read_work_records(self.data_dir)
        self.assertEqual(len(state["records"]), 1)
        self.assertEqual(state["records"][0]["revision"], 1)
        self.assertEqual(state["records"][0]["display_id"], "R-261105-AAAAAAAAAAAA")
        original = {p.name: p.read_bytes() for p in
                    (self.data_dir / "work_archive" / "record_events").glob("*.json")}
        app.append_work_record_event(self.data_dir, work_event(
            "work-update-0001", "update", 1,
            {"occurred_on": "2026-11-01", "outcome": "已解决", "duration_minutes": 55}))
        revised = app.read_work_records(self.data_dir)["records"][0]
        self.assertEqual(revised["revision"], 2)
        self.assertEqual(revised["occurred_on"], "2026-11-01")
        self.assertEqual(revised["outcome"], "已解决")
        self.assertEqual(revised["display_id"], state["records"][0]["display_id"])
        self.assertEqual(original["evt_work-create-0001.json"],
                         (self.data_dir / "work_archive" / "record_events" /
                          "evt_work-create-0001.json").read_bytes())
        self.assertEqual(legacy_bytes, {p.name: p.read_bytes()
                                       for p in (self.data_dir / "events").glob("*.json")})
        self.assertEqual(app.read_workspace(self.data_dir)["tasks"][0]["status"], "todo")

    def test_legacy_record_defaults_to_progress_and_decision_updates_keep_same_record_id(self):
        app.append_work_record_event(self.data_dir, work_event())
        first = app.read_work_records(self.data_dir)["records"][0]
        self.assertEqual(first["record_type"], "progress")
        app.append_work_record_event(self.data_dir, work_event(
            "work-decision-update", "update", 1,
            {"record_type": "decision", "outcome": "不卖"}))
        revised = app.read_work_records(self.data_dir)["records"][0]
        self.assertEqual(revised["record_type"], "decision")
        self.assertEqual(revised["outcome"], "不卖")
        self.assertEqual(revised["record_id"], first["record_id"])
        self.assertEqual(revised["revision"], 2)

    def test_conflict_bad_event_and_partial_sync_fail_closed(self):
        app.append_work_record_event(self.data_dir, work_event())
        app.append_work_record_event(self.data_dir, work_event(
            "work-update-0001", "update", 1, {"outcome": "A"}))
        app.append_work_record_event(self.data_dir, work_event(
            "work-update-0002", "update", 1, {"outcome": "B"}))
        record = app.read_work_records(self.data_dir)["records"][0]
        self.assertTrue(record["conflict"])
        self.assertEqual(record["revision"], 1)
        self.assertIsNone(record["outcome"])
        directory = self.data_dir / "work_archive" / "record_events"
        (directory / "corrupt.json").write_text('{"version":1,', encoding="utf-8")
        self.assertTrue(any("corrupt.json" in message
                            for message in app.read_work_records(self.data_dir)["warnings"]))

    def test_duplicate_event_id_cross_record_marks_both_conflicted(self):
        app.append_work_record_event(self.data_dir, work_event())
        other_id = "RECORD-" + "C" * 32
        app.append_work_record_event(self.data_dir, work_event(
            "work-other-0001", record_id=other_id))
        # Remote cloud sync can deliver the same event_id under a second filename.
        duplicate = work_event("work-create-0001", "update", 1, {"outcome": "conflict"},
                               record_id=other_id)
        directory = self.data_dir / "work_archive" / "record_events"
        (directory / "different-name.json").write_text(json.dumps(duplicate), encoding="utf-8")
        records = app.read_work_records(self.data_dir)["records"]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(item["conflict"] for item in records))

    def test_task_completion_is_read_only_and_not_copied_into_records(self):
        app.append_event(self.data_dir, task_event("old-create-0001", "create", 0,
                          {"title": "虚构采购任务", "status": "todo"}))
        app.append_event(self.data_dir, task_event("old-done-0001", "update", 1,
                          {"status": "done"}, done=True))
        workspace = app.read_workspace(self.data_dir)
        activity = app.read_task_completion_activity(self.data_dir, workspace)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["task_title"], "虚构采购任务")
        self.assertEqual(activity[0]["source_event_id"], "old-done-0001")
        self.assertEqual(app.read_work_records(self.data_dir)["records"], [])
        self.assertFalse((self.data_dir / "work_archive").exists())


class WorkRecordHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        app.append_event(self.data_dir, task_event("old-create-0001", "create", 0,
                         {"title": "虚构采购任务", "status": "todo"}))
        project_event = {"version": 1, "event_id": "work-project-0001",
                         "project_id": PROJECT, "action": "create", "actor": "user",
                         "timestamp": "2026-11-05T00:00:00Z", "base_revision": 0,
                         "changes": {"name": "虚构设备项目"}}
        app.append_project_event(self.data_dir, project_event)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                         app.handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def call(self, method, path, payload=None, headers=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base + path, data=data, method=method,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_create_edit_get_and_conflict(self):
        body = {"content": "临时沟通了设备交期", "occurred_on": "2026-10-30",
                "project_id": PROJECT, "task_id": TASK,
                "outcome": "双方达成一致", "duration_minutes": 30}
        code, created = self.call("POST", "/api/work-records", body)
        self.assertEqual(code, 201, created)
        self.assertTrue(created["record_id"].startswith("RECORD-"))
        self.assertEqual(created["revision"], 1)
        code, state = self.call("GET", "/api/work-records")
        self.assertEqual(code, 200)
        self.assertEqual(len(state["records"]), 1)
        self.assertEqual(state["records"][0]["project_name"], "虚构设备项目")
        self.assertEqual(state["records"][0]["task_title"], "虚构采购任务")
        endpoint = "/api/work-records/" + created["record_id"] + "/update"
        code, saved = self.call("POST", endpoint, {**body, "revision": 1,
                                                 "occurred_on": "2026-11-01"})
        self.assertEqual(code, 200, saved)
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["display_id"], created["display_id"])
        self.assertEqual(self.call("POST", endpoint, {**body, "revision": 1})[0], 409)
        code, state = self.call("GET", "/api/work-records")
        self.assertEqual(state["records"][0]["revision"], 2)
        self.assertEqual(state["records"][0]["occurred_on"], "2026-11-01")
        self.assertEqual(len(list((self.data_dir / "work_archive" / "record_events").glob("*.json"))), 2)

    def test_invalid_bad_links_and_external_origin_have_no_write(self):
        base = {"content": "记录事实", "occurred_on": "2026-11-05"}
        self.assertEqual(self.call("POST", "/api/work-records",
                                   {**base, "status": "done"})[0], 400)
        self.assertEqual(self.call("POST", "/api/work-records",
                                   {**base, "project_id": "PROJECT-" + "F" * 32})[0], 409)
        self.assertEqual(self.call("POST", "/api/work-records",
                                   {**base, "task_id": "TASK-UNKNOWN"})[0], 409)
        self.assertEqual(self.call("POST", "/api/work-records", base,
                                   {"Origin": "https://outside.example"})[0], 403)
        self.assertFalse((self.data_dir / "work_archive").exists())

    def test_read_only_task_completion_activity(self):
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"completion-task-context-001",
            "object_type":"task","object_id":TASK,"action":"set","actor":"user",
            "timestamp":"2026-11-05T06:00:00Z","base_revision":0,
            "changes":{"description":"任务背景：确认本期事项已处理"}})
        app.append_event(self.data_dir, task_event("old-done-0001", "update", 1,
                                                   {"status": "done"}, done=True))
        _, payload = self.call("GET", "/api/work-records")
        self.assertEqual(len(payload["task_completions"]), 1)
        self.assertEqual(payload["records"], [])
        code, preview = self.call("GET",
            "/api/work-archive/preview?period=daily&day=2026-11-05")
        self.assertEqual(code, 200)
        self.assertEqual(preview["record_count"], 0)
        self.assertEqual(preview["completion_count"], 1)
        self.assertEqual(preview["object_contexts"][0]["object_type"], "task")
        self.assertIn("任务背景：确认本期事项已处理", preview["body"])

    def test_decision_record_type_flows_into_preview_and_rejects_unknown_type(self):
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"summary-project-context-001",
            "object_type":"project","object_id":PROJECT,"action":"set","actor":"user",
            "timestamp":"2026-11-11T00:00:00Z","base_revision":0,
            "changes":{"description":"项目背景：评估零件处置事项"}})
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"summary-task-context-001",
            "object_type":"task","object_id":TASK,"action":"set","actor":"user",
            "timestamp":"2026-11-11T00:01:00Z","base_revision":0,
            "changes":{"description":"任务目标：判断是否转卖零件"}})
        body = {"content": "评估是否向供应商转卖零件", "occurred_on": "2026-11-11",
                "record_type": "decision", "outcome": "不卖",
                "project_id": PROJECT, "task_id": TASK}
        code, created = self.call("POST", "/api/work-records", body)
        self.assertEqual(code, 201, created)
        _, state = self.call("GET", "/api/work-records")
        self.assertEqual(state["records"][0]["record_type"], "decision")
        immutable_code, immutable = self.call(
            "POST", "/api/work-records/" + created["record_id"] + "/update", {
                "revision": 1, "content": "改为出售", "outcome": "卖"})
        self.assertEqual(immutable_code, 409)
        self.assertIn("immutable", immutable["error"])
        endpoint = ("/api/work-archive/preview?period=daily&day=2026-11-11&project_id=" + PROJECT)
        code, preview = self.call("GET", endpoint)
        self.assertEqual(code, 200)
        self.assertEqual(preview["record_sources"][0]["record_type"], "decision")
        self.assertIn("[决策／结论]", preview["body"])
        self.assertIn("结论：不卖", preview["body"])
        self.assertEqual({item["object_type"] for item in preview["object_contexts"]},
                         {"project", "task"})
        self.assertEqual(len(preview["record_sources"]), 1)
        self.assertEqual(preview["record_count"], 1,
                         "object descriptions are context, not work events")
        self.assertIn("项目背景：评估零件处置事项", preview["body"])
        self.assertIn("任务目标：判断是否转卖零件", preview["body"])
        analysis = app.work_analysis_context(
            self.data_dir, app.read_workspace(self.data_dir), "daily", "2026-11-11", PROJECT)
        self.assertIn("项目背景：评估零件处置事项", analysis["prompt"])
        code, updated_description = self.call("POST", "/api/object-details", {
            "object_type":"task","object_id":TASK,"revision":1,
            "description":"任务目标：重新评估转卖零件"})
        self.assertEqual(code, 200, updated_description)
        code, refreshed = self.call("GET", endpoint)
        self.assertEqual(code, 200)
        self.assertNotEqual(preview["source_digest"], refreshed["source_digest"])
        self.assertIn("任务目标：重新评估转卖零件", refreshed["body"])
        self.assertEqual(self.call("POST", "/api/work-records",
            {**body, "record_type": "unrecognized"})[0], 400)

    def test_object_descriptions_use_separate_revisioned_events(self):
        task_event_bytes = {p.name:p.read_bytes() for p in (self.data_dir / "events").glob("*.json")}
        project_event_bytes = {p.name:p.read_bytes() for p in
                               (self.data_dir / "project_events").glob("*.json")}
        step_id = "STEP-" + "C" * 32
        app.append_step_event(self.data_dir, {
            "version":1,"event_id":"work-step-create-0001","task_id":TASK,
            "step_id":step_id,"action":"create","actor":"user",
            "timestamp":"2026-11-11T00:00:00Z","base_revision":0,
            "changes":{"title":"虚构步骤","position":1}})
        step_event_bytes = {p.name:p.read_bytes() for p in
                            (self.data_dir / "step_events").glob("*.json")}
        code, saved = self.call("POST", "/api/object-details", {
            "object_type":"project","object_id":PROJECT,"revision":0,
            "description":"项目背景"})
        self.assertEqual(code, 200, saved)
        self.assertEqual(saved["revision"], 1)
        code, saved = self.call("POST", "/api/object-details", {
            "object_type":"task","object_id":TASK,"revision":0,
            "description":"任务目标"})
        self.assertEqual(code, 200, saved)
        code, saved = self.call("POST", "/api/object-details", {
            "object_type":"step","object_id":step_id,"task_id":TASK,
            "revision":0,"description":"步骤说明"})
        self.assertEqual(code, 200, saved)
        self.assertEqual(self.call("POST", "/api/object-details", {
            "object_type":"step","object_id":step_id,"task_id":"TASK-WRONG",
            "revision":0,"description":"错误父任务"})[0], 404)
        self.assertEqual(self.call("POST", "/api/object-details", {
            "object_type":"task","object_id":TASK,"revision":0,
            "description":"过期覆盖"})[0], 409)
        code, workspace = self.call("GET", "/api/tasks")
        self.assertEqual(code, 200)
        self.assertEqual(workspace["projects"][0]["description"], "项目背景")
        task = next(item for item in workspace["tasks"] if item["task_id"] == TASK)
        self.assertEqual(task["description"], "任务目标")
        self.assertEqual(task["steps"][0]["description"], "步骤说明")
        code, cleared = self.call("POST", "/api/object-details", {
            "object_type":"project","object_id":PROJECT,"revision":1,"description":""})
        self.assertEqual(code, 200, cleared)
        self.assertEqual(cleared["revision"], 2)
        self.assertEqual(task_event_bytes, {p.name:p.read_bytes()
                                           for p in (self.data_dir / "events").glob("*.json")})
        self.assertEqual(project_event_bytes, {p.name:p.read_bytes()
                                              for p in (self.data_dir / "project_events").glob("*.json")})
        self.assertEqual(step_event_bytes, {p.name:p.read_bytes()
                                           for p in (self.data_dir / "step_events").glob("*.json")})
        _, records = self.call("GET", "/api/work-records")
        self.assertEqual(records["records"], [], "object descriptions are not work records")
        _, cleared_workspace = self.call("GET", "/api/tasks")
        self.assertEqual(cleared_workspace["projects"][0]["description"], "")
        self.assertEqual(len(list((self.data_dir / "work_archive" /
                                   "object_detail_events").glob("*.json"))), 4)

    def test_object_description_concurrent_revisions_freeze_only_target(self):
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"object-task-desc-0001","object_type":"task",
            "object_id":TASK,"action":"set","actor":"user",
            "timestamp":"2026-11-11T00:00:00Z","base_revision":0,
            "changes":{"description":"版本 A"}})
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"object-task-desc-0002","object_type":"task",
            "object_id":TASK,"action":"set","actor":"user",
            "timestamp":"2026-11-11T00:01:00Z","base_revision":0,
            "changes":{"description":"版本 B"}})
        app.append_object_detail_event(self.data_dir, {
            "version":1,"event_id":"object-project-desc-0001","object_type":"project",
            "object_id":PROJECT,"action":"set","actor":"user",
            "timestamp":"2026-11-11T00:02:00Z","base_revision":0,
            "changes":{"description":"项目说明"}})
        workspace = app.read_workspace(self.data_dir)
        task = next(item for item in workspace["tasks"] if item["task_id"] == TASK)
        project = next(item for item in workspace["projects"] if item["project_id"] == PROJECT)
        self.assertTrue(task["description_conflict"])
        self.assertEqual(task["description"], "")
        self.assertFalse(project["description_conflict"])
        self.assertEqual(project["description"], "项目说明")
        self.assertEqual(task["status"], "todo")


if __name__ == "__main__":
    unittest.main()
