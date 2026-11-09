"""Unified progress timeline and per-report source selection; synthetic data only."""
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


PROJECT = "PROJECT-" + "A" * 32
TASK = "TASK-TEST-PROGRESS"
STEP = "STEP-" + "B" * 32
STAMP = "2026-11-09T08:00:00Z"


class UnifiedTimelineReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        app.append_project_event(self.root, {
            "version": 1, "event_id": "progress-project-create",
            "project_id": PROJECT, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"name": "虚构采购项目"}})
        app.append_event(self.root, {
            "version": 1, "event_id": "progress-task-create",
            "task_id": TASK, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"title": "虚构报价回收", "status": "todo", "project_id": PROJECT}})
        app.append_step_event(self.root, {
            "version": 1, "event_id": "progress-step-create",
            "task_id": TASK, "step_id": STEP, "action": "create",
            "actor": "user", "timestamp": STAMP, "base_revision": 0,
            "changes": {"title": "催问供应商", "position": 1}})
        self.original_task = {p.name: p.read_bytes() for p in
                              (self.root / "events").glob("*.json")}
        self.original_step = {p.name: p.read_bytes() for p in
                              (self.root / "step_events").glob("*.json")}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.root))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def call(self, method, path, payload=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = Request(self.base + path, data=data, method=method,
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, json.load(res)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def create_facts(self):
        code, project_fact = self.call("POST", "/api/work-records", {
            "content": "上午完成常规内部例会", "occurred_on": "2026-11-09",
            "project_id": PROJECT, "task_id": TASK})
        self.assertEqual(code, 201)
        code, step_fact = self.call("POST", "/api/work-records", {
            "content": "下午催问设备报价，对方仍在确认货源",
            "occurred_on": "2026-11-09", "project_id": PROJECT,
            "task_id": TASK,
            "outcome": "取得回复但没有正式报价",
            "action_links": [{"target_type": "step", "target_id": STEP,
                              "task_id": TASK, "relation": "progress_on"},
                             {"target_type": "task", "target_id": TASK,
                              "relation": "progress_on"}]})
        self.assertEqual(code, 201)
        return project_fact["record_id"], step_fact["record_id"]

    def test_scope_fact_single_copy_and_report_selects_only_important(self):
        regular, important = self.create_facts()
        path = "/api/work-archive/preview?" + urlencode({
            "period": "daily", "day": "2026-11-09", "project_id": PROJECT})
        code, preview = self.call("GET", path)
        self.assertEqual(code, 200)
        self.assertEqual(preview["record_count"], 2, "multi-linked fact counted once")
        self.assertEqual(set(preview["source_record_ids"]), {regular, important})
        self.assertEqual(len(preview["record_sources"]), 2)
        record = next(r for r in preview["record_sources"] if r["record_id"] == important)
        self.assertEqual(record["outcome"], "取得回复但没有正式报价")
        payload = {
            "period": "daily", "day": "2026-11-09", "project_id": PROJECT,
            "body": "# 汇报版\n只选入重要沟通事实", "confirmed": True,
            "source_record_ids": preview["source_record_ids"],
            "source_completion_ids": preview["source_completion_ids"],
            "audience": "report",
            "included_record_ids": [important],
            "included_completion_ids": []
        }
        self.assertEqual(self.call("POST", "/api/work-archive/summaries", payload)[0], 201)
        _, state = self.call("GET", "/api/work-archive")
        summary = state["summaries"][0]
        self.assertEqual(summary["audience"], "report")
        self.assertEqual(summary["included_record_ids"], [important])
        self.assertEqual(set(summary["source_record_ids"]), {regular, important})
        self.assertEqual(len(app.read_work_records(self.root)["records"]), 2)
        self.assertEqual(app.read_workspace(self.root)["tasks"][0]["status"], "todo")
        self.assertEqual(self.original_task, {p.name: p.read_bytes()
                                              for p in (self.root / "events").glob("*.json")})
        self.assertEqual(self.original_step, {p.name: p.read_bytes()
                                              for p in (self.root / "step_events").glob("*.json")})

    def test_invalid_selection_and_source_changes_fail_closed(self):
        regular, important = self.create_facts()
        _, preview = self.call("GET", "/api/work-archive/preview?period=daily&day=2026-11-09")
        base = {"period": "daily", "day": "2026-11-09", "project_id": None,
                "body": "真实工作来源", "confirmed": False,
                "source_record_ids": preview["source_record_ids"],
                "source_completion_ids": preview["source_completion_ids"],
                "audience": "report", "included_record_ids": [important],
                "included_completion_ids": []}
        for bad in (
            base | {"included_record_ids": [important, important]},
            base | {"included_record_ids": ["RECORD-" + "F" * 32]},
            base | {"audience": "machine"},
            {k: v for k, v in base.items() if k != "included_completion_ids"},
        ):
            with self.subTest(bad=bad):
                self.assertEqual(self.call("POST", "/api/work-archive/summaries", bad)[0], 400)
        self.assertFalse((self.root / "work_archive" / "summary_events").exists())
        self.assertEqual(self.call("POST", "/api/work-records", {
            "content": "晚到的新增沟通", "occurred_on": "2026-11-09"})[0], 201)
        self.assertEqual(self.call("POST", "/api/work-archive/summaries", base)[0], 409)
        self.assertFalse((self.root / "work_archive" / "summary_events").exists())

    def test_legacy_summary_without_audience_is_personal_all_sources(self):
        regular, _ = self.create_facts()
        event = {"version": 1, "event_id": "legacy-summary-create",
                 "summary_id": "SUMMARY-" + "D" * 32, "action": "create",
                 "actor": "user", "timestamp": STAMP, "base_revision": 0,
                 "changes": {"period": "daily", "period_start": "2026-11-09",
                             "period_end": "2026-11-09", "project_id": None,
                             "body": "旧版个人日志", "confirmed": False,
                             "source_record_ids": [regular],
                             "source_completion_ids": []}}
        app.append_work_archive_event(self.root, "summary", event)
        _, state = self.call("GET", "/api/work-archive")
        legacy = state["summaries"][0]
        self.assertEqual(legacy["audience"], "personal")
        self.assertEqual(legacy["included_record_ids"], [regular])
        self.assertEqual(legacy["source_record_ids"], [regular])


if __name__ == "__main__":
    unittest.main()
