"""Extended work archive integration tests: all data are synthetic and isolated."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import app

TASK = "TASK-WORK-ARCHIVE-TEST"
STEP = "STEP-" + "B" * 32
PROJECT = "PROJECT-" + "C" * 32
RECORD = "RECORD-" + "A" * 32
INBOX = "INBOX-" + "D" * 32
SUMMARY = "SUMMARY-" + "E" * 32
STAMP = "2026-11-05T06:30:00Z"


def event(kind, action, revision, changes, *, eid="archive-test-0001", ident=None):
    key = "inbox_id" if kind == "inbox" else "summary_id"
    return {"version": 1, "event_id": eid, key: ident or
            (INBOX if kind == "inbox" else SUMMARY), "action": action,
            "actor": "user", "timestamp": STAMP, "base_revision": revision,
            "changes": changes}


def record_event(changes, *, eid="record-new-0001", action="create", revision=0):
    return {"version": 1, "event_id": eid, "record_id": RECORD,
            "action": action, "actor": "user", "timestamp": STAMP,
            "base_revision": revision, "changes": changes}


class WorkArchiveContractTests(unittest.TestCase):
    def test_date_boundaries_and_archive_schema(self):
        self.assertEqual(app.work_review_period("weekly", "2026-01-01"),
                         ("2025-12-29", "2026-01-04"))
        self.assertEqual(app.work_review_period("monthly", "2028-02-29"),
                         ("2028-02-01", "2028-02-29"))
        self.assertEqual(app.work_review_period("daily", "2026-11-05"),
                         ("2026-11-05", "2026-11-05"))
        for bad_day in ("2026-02-29", "not-a-day", "2026-11-5"):
            with self.subTest(day=bad_day), self.assertRaises(ValueError):
                app.work_review_period("daily", bad_day)
        with self.assertRaises(ValueError):
            app.work_review_period("yearly", "2026-11-05")
        source = event("inbox", "create", 0, {
            "content": "临时会议和设备采购沟通", "occurred_on": None, "project_id": None
        })
        self.assertEqual(app.validate_work_archive_event(source, "inbox"), source)
        for bad in (
            {**source, "status": "done"},
            {**source, "actor": "machine"},
            {**source, "timestamp": "2026-11-05"},
            {**source, "changes": {"content": " ", "occurred_on": None}},
            {**source, "changes": {"content": "会议", "occurred_on": "2026-02-29"}},
            event("inbox", "dismiss", 1, {"ignored": True}, eid="bad-dismiss-0001") |
                {"actor": "chatgpt"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                app.validate_work_archive_event(bad, "inbox")
        self.assertEqual(app.validate_work_archive_event(
            event("inbox", "dismiss", 1, {"ignored": True}, eid="dismiss-ok-0001"), "inbox"
        )["action"], "dismiss")

    def test_multilink_evidence_and_source_strict_validation(self):
        base = {"content": "已处理沟通，形成行动", "occurred_on": "2026-11-04",
                "action_links": [
                    {"target_type": "task", "target_id": TASK, "relation": "progress_on"},
                    {"target_type": "step", "target_id": STEP, "task_id": TASK,
                     "relation": "result_of"}],
                "evidence_links": [{"title": "虚构会议纪要",
                                    "url": "https://drive.google.com/file/d/test/view"}],
                "featured": True, "source_inbox_id": INBOX}
        app.validate_work_record_event(record_event(base))
        for bad in (
            base | {"featured": 1},
            base | {"source_inbox_id": "INBOX-??"},
            base | {"action_links": [{"target_type": "step", "target_id": STEP,
                                     "relation": "progress_on"}]},
            base | {"action_links": [
                {"target_type": "task", "target_id": TASK, "relation": "progress_on"},
                {"target_type": "task", "target_id": TASK, "relation": "result_of"}]},
            base | {"action_links": [{"target_type": "task", "target_id": TASK,
                                     "relation": "unknown"}]},
            base | {"evidence_links": [{"title": "不可信链接",
                                       "url": "https://outside.example/document"}]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                app.validate_work_record_event(record_event(bad))
        with self.assertRaises(ValueError):
            app.validate_work_record_event(record_event(
                {"source_inbox_id": INBOX}, eid="work-update-0001",
                action="update", revision=1))


class WorkArchiveHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        app.append_project_event(self.dir, {
            "version": 1, "event_id": "archive-project-0001",
            "project_id": PROJECT, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"name": "虚构新设备项目"}})
        app.append_event(self.dir, {
            "version": 1, "event_id": "archive-task-create-0001", "task_id": TASK,
            "action": "create", "actor": "user", "timestamp": STAMP,
            "base_revision": 0, "changes": {"title": "虚构设备采购任务", "status": "todo",
                                           "project_id": PROJECT}})
        app.append_step_event(self.dir, {
            "version": 1, "event_id": "archive-step-create-0001", "task_id": TASK,
            "step_id": STEP, "action": "create", "actor": "user", "timestamp": STAMP,
            "base_revision": 0, "changes": {"title": "核对交期", "position": 1}})
        self.task_bytes = {p.name: p.read_bytes()
                           for p in (self.dir / "events").glob("*.json")}
        self.step_bytes = {p.name: p.read_bytes()
                           for p in (self.dir / "step_events").glob("*.json")}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def call(self, method, path, payload=None, headers=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base + path, data=data, method=method,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_inbox_source_to_linked_record_is_idempotent_and_append_only(self):
        _, initial = self.call("GET", "/api/work-archive")
        self.assertEqual(initial["inbox"], [])
        self.assertEqual(initial["summaries"], [])
        payload = {"content": "先记录原始沟通信息", "occurred_on": None,
                   "project_id": PROJECT}
        self.assertEqual(self.call("POST", "/api/work-archive/inbox",
                                   payload | {"status": "done"})[0], 400)
        self.assertEqual(self.call("POST", "/api/work-archive/inbox",
                                   payload, {"Origin": "https://outside.example"})[0], 403)
        self.assertFalse((self.dir / "work_archive").exists())
        code, created = self.call("POST", "/api/work-archive/inbox", payload)
        self.assertEqual(code, 201, created)
        inbox_id = created["inbox_id"]
        record_payload = {
            "content": "补记：实际已经解决采购交期问题",
            "occurred_on": "2026-11-04",
            "project_id": PROJECT, "task_id": TASK,
            "action_links": [{"target_type": "task", "target_id": TASK,
                              "relation": "progress_on"},
                             {"target_type": "step", "task_id": TASK, "target_id": STEP,
                              "relation": "result_of"}],
            "featured": True, "outcome": "供应商确认按约定供货",
            "evidence_links": [{"title": "虚构报价清单",
                                "url": "https://drive.google.com/file/d/fiction/view"}],
            "source_inbox_id": inbox_id
        }
        code, stored = self.call("POST", "/api/work-records", record_payload)
        self.assertEqual(code, 201, stored)
        self.assertEqual(self.call("POST", "/api/work-records", record_payload)[0], 409,
                         "retrying an already processed source must not duplicate a fact")
        _, state = self.call("GET", "/api/work-archive")
        self.assertEqual(state["inbox"][0]["processed_record_id"], stored["record_id"])
        self.assertEqual(self.call("POST", "/api/work-archive/inbox/" + inbox_id +
                                   "/ignore", {"revision": 1, "confirmed_ignore": True})[0], 409)
        _, records = self.call("GET", "/api/work-records")
        r = records["records"][0]
        self.assertEqual(len(r["action_link_labels"]), 2)
        self.assertTrue(all(x["label"] for x in r["action_link_labels"]))
        self.assertTrue(r["featured"])
        self.assertEqual(r["evidence_links"][0]["title"], "虚构报价清单")
        self.assertEqual(self.task_bytes, {p.name: p.read_bytes()
                                         for p in (self.dir / "events").glob("*.json")})
        self.assertEqual(self.step_bytes, {p.name: p.read_bytes()
                                         for p in (self.dir / "step_events").glob("*.json")})
        self.assertEqual(len(list((self.dir / "work_archive" /
                                   "record_events").glob("*.json"))), 1)

    def test_inbox_ignore_is_audit_only_and_prevents_reuse(self):
        _, new = self.call("POST", "/api/work-archive/inbox", {
            "content": "会议想法尚未核实", "occurred_on": None})
        url = "/api/work-archive/inbox/" + new["inbox_id"] + "/ignore"
        self.assertEqual(self.call("POST", url,
                                   {"revision": 1, "confirmed_ignore": False})[0], 400)
        self.assertEqual(self.call("POST", url,
                                   {"revision": 1, "confirmed_ignore": True})[0], 200)
        self.assertEqual(self.call("POST", url,
                                   {"revision": 1, "confirmed_ignore": True})[0], 409)
        _, state = self.call("GET", "/api/work-archive")
        self.assertTrue(state["inbox"][0]["ignored"])
        self.assertEqual(len(list((self.dir / "work_archive" /
                                   "inbox_events").glob("*.json"))), 2)
        self.assertEqual(self.call("POST", "/api/work-records", {
            "content": "不应允许以忽略来源补录", "occurred_on": "2026-11-05",
            "source_inbox_id": new["inbox_id"]})[0], 409)

    def test_summary_preview_save_edit_sources_and_conflicts(self):
        code, created = self.call("POST", "/api/work-records", {
            "content": "11月5日核对虚构交期", "occurred_on": "2026-11-05",
            "project_id": PROJECT, "outcome": "确认下一步方案",
            "duration_minutes": 40})
        self.assertEqual(code, 201, created)
        app.append_event(self.dir, {
            "version": 1, "event_id": "archive-task-done-0001",
            "task_id": TASK, "action": "update", "actor": "user",
            "timestamp": STAMP, "base_revision": 1,
            "changes": {"status": "done"}, "confirmed_done": True})
        qs = urlencode({"period": "weekly", "day": "2026-11-05", "project_id": PROJECT})
        code, preview = self.call("GET", "/api/work-archive/preview?" + qs)
        self.assertEqual(code, 200)
        self.assertEqual(preview["period_start"], "2026-11-02")
        self.assertEqual(preview["period_end"], "2026-11-08")
        self.assertEqual(preview["record_count"], 1)
        self.assertEqual(preview["completion_count"], 1)
        self.assertEqual(preview["duration_minutes"], 40)
        self.assertIn("非 AI 自动分析", preview["body"])
        self.assertEqual(preview["source_record_ids"], [created["record_id"]])
        self.assertFalse((self.dir / "work_archive" / "summary_events").exists(),
                         "read-only preview never writes")
        body = {"period": "weekly", "day": "2026-11-05",
                "project_id": PROJECT, "body": preview["body"] + "\n人工确认：后续继续推进",
                "confirmed": False, "source_record_ids": preview["source_record_ids"],
                "source_completion_ids": preview["source_completion_ids"]}
        self.assertEqual(self.call("POST", "/api/work-archive/summaries",
                                   body | {"source_record_ids": []})[0], 409)
        code, saved = self.call("POST", "/api/work-archive/summaries", body)
        self.assertEqual(code, 201, saved)
        path = "/api/work-archive/summaries/" + saved["summary_id"] + "/update"
        code, updated = self.call("POST", path, {"revision": 1,
                                               "body": body["body"] + "\n复盘结论",
                                               "confirmed": True})
        self.assertEqual(code, 200, updated)
        self.assertEqual(self.call("POST", path, {"revision": 1,
                                                "confirmed": False})[0], 409)
        _, state = self.call("GET", "/api/work-archive")
        self.assertEqual(state["summaries"][0]["revision"], 2)
        self.assertTrue(state["summaries"][0]["confirmed"])
        self.assertEqual(state["summaries"][0]["source_record_ids"],
                         preview["source_record_ids"])
        self.assertEqual(len(list((self.dir / "work_archive" /
                                   "summary_events").glob("*.json"))), 2)
        self.assertEqual(self.task_bytes.keys(), {p.name for p in
                                                   (self.dir / "events").glob("*.json")
                                                   if p.name in self.task_bytes})

    def test_summary_missing_period_and_archive_conflicts(self):
        for query in ("period=yearly&day=2026-11-05",
                      "period=weekly&day=2026-02-29",
                      "period=monthly&day=2026-11-05&project_id=PROJECT-" + "F"*32):
            self.assertNotEqual(self.call("GET", "/api/work-archive/preview?" + query)[0], 200)
        first = event("inbox", "create", 0, {
            "content": "原文不能覆盖", "occurred_on": None})
        app.append_work_archive_event(self.dir, "inbox", first)
        second = event("inbox", "dismiss", 1, {"ignored": True}, eid="ignore-first-001")
        third = event("inbox", "dismiss", 1, {"ignored": True}, eid="ignore-second-002")
        app.append_work_archive_event(self.dir, "inbox", second)
        app.append_work_archive_event(self.dir, "inbox", third)
        state = app.read_work_inbox(self.dir)
        self.assertTrue(state["items"][0]["conflict"])
        self.assertTrue(any("concurrent" in warning for warning in state["warnings"]))


if __name__ == "__main__":
    unittest.main()
