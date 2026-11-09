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
            "audience": "report", "source_digest": preview["source_digest"],
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

    def test_source_cards_show_business_context_and_digest_tracks_project_rename(self):
        ordinary, important = self.create_facts()
        endpoint = "/api/work-archive/preview?period=daily&day=2026-11-09"
        code, first = self.call("GET", endpoint)
        self.assertEqual(code, 200)
        row = next(r for r in first["record_sources"]
                   if r["record_id"] == important)
        self.assertEqual(row["project_name"], "虚构采购项目")
        self.assertEqual(row["task_title"], "虚构报价回收")
        self.assertEqual(row["revision"], 1)
        self.assertIn("催问供应商",
                      " ".join(x["label"] for x in row["action_link_labels"]))
        self.assertEqual(len(first["source_record_ids"]), 2,
                         "step plus task associations must not duplicate the record")
        sid, saved_preview = self._save_report(record_id=important)
        self.assertEqual(first["source_digest"], saved_preview["source_digest"])
        app.append_project_event(self.root, {
            "version": 1, "event_id": "progress-project-rename",
            "project_id": PROJECT, "action": "update", "actor": "user",
            "timestamp": STAMP, "base_revision": 1,
            "changes": {"name": "虚构设备升级项目"}})
        _, second = self.call("GET", endpoint)
        self.assertEqual(second["source_record_ids"], first["source_record_ids"])
        self.assertEqual(next(r for r in second["record_sources"]
                             if r["record_id"] == ordinary)["project_name"],
                         "虚构设备升级项目")
        self.assertNotEqual(first["source_digest"], second["source_digest"],
                            "context changes must invalidate an old source snapshot")
        url = "/api/work-archive/summaries/" + sid + "/reselect"
        self.assertEqual(self.call("POST", url,
                         self._reselect_payload(1, saved_preview, included=[important]))[0], 409)
        self.assertEqual(len(list((self.root / "work_archive" /
                                  "summary_events").glob("*.json"))), 1)

    def test_invalid_selection_and_source_changes_fail_closed(self):
        regular, important = self.create_facts()
        _, preview = self.call("GET", "/api/work-archive/preview?period=daily&day=2026-11-09")
        base = {"period": "daily", "day": "2026-11-09", "project_id": None,
                "body": "真实工作来源", "confirmed": False,
                "source_record_ids": preview["source_record_ids"],
                "source_completion_ids": preview["source_completion_ids"],
                "audience": "report", "source_digest": preview["source_digest"],
                "included_record_ids": [important],
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

    def _save_report(self, *, record_id=None):
        _, preview = self.call("GET", "/api/work-archive/preview?period=daily&day=2026-11-09")
        included = [record_id] if record_id else []
        code, saved = self.call("POST", "/api/work-archive/summaries", {
            "period": "daily", "day": "2026-11-09", "project_id": None,
            "body": "已人工确认旧总结", "confirmed": True,
            "audience": "report", "source_digest": preview["source_digest"],
            "source_record_ids": preview["source_record_ids"],
            "source_completion_ids": preview["source_completion_ids"],
            "included_record_ids": included, "included_completion_ids": []})
        self.assertEqual(code, 201, saved)
        return saved["summary_id"], preview

    def _reselect_payload(self, revision, preview, *, included=None):
        return {"revision": revision, "audience": "report",
                "body": "# 新版汇报\n人工审核后只保留所选来源", "confirmed": False,
                "confirmed_reselect": True,
                "source_digest": preview["source_digest"],
                "source_record_ids": preview["source_record_ids"],
                "source_completion_ids": preview["source_completion_ids"],
                "included_record_ids": included or [], "included_completion_ids": []}

    def test_reselect_history_appends_new_revision_while_preserving_old_bytes(self):
        ordinary, important = self.create_facts()
        summary_id, original = self._save_report(record_id=important)
        directory = self.root / "work_archive" / "summary_events"
        old_files = {p.name: p.read_bytes() for p in directory.glob("*.json")}
        # The saved report has already been checked. Reselection must unconfirm it.
        code, updated = self.call("POST",
                                  "/api/work-archive/summaries/" + summary_id + "/reselect",
                                  self._reselect_payload(1, original, included=[ordinary]))
        self.assertEqual(code, 200, updated)
        self.assertEqual(updated["revision"], 2)
        _, state = self.call("GET", "/api/work-archive")
        summary = state["summaries"][0]
        self.assertEqual(summary["revision"], 2)
        self.assertEqual(summary["included_record_ids"], [ordinary])
        self.assertEqual(set(summary["source_record_ids"]), {ordinary, important})
        self.assertEqual(summary["audience"], "report")
        self.assertFalse(summary["confirmed"], "new source set must be reviewed again")
        self.assertEqual(len(list(directory.glob("*.json"))), 2)
        for name, data in old_files.items():
            self.assertEqual((directory / name).read_bytes(), data)
        self.assertEqual(self.original_task, {p.name: p.read_bytes()
                                              for p in (self.root / "events").glob("*.json")})
        self.assertEqual(self.original_step, {p.name: p.read_bytes()
                                              for p in (self.root / "step_events").glob("*.json")})
        self.assertEqual(len(app.read_work_records(self.root)["records"]), 2)
        self.assertEqual(self.call("POST",
            "/api/work-archive/summaries/" + summary_id + "/reselect",
            self._reselect_payload(1, original, included=[important]))[0], 409)

    def test_reselect_requires_explicit_approval_and_valid_source_ids(self):
        ordinary, important = self.create_facts()
        summary_id, preview = self._save_report(record_id=important)
        url = "/api/work-archive/summaries/" + summary_id + "/reselect"
        valid = self._reselect_payload(1, preview, included=[ordinary])
        for bad in (
            {**valid, "confirmed_reselect": False},
            {**valid, "confirmed": True},
            {**valid, "included_record_ids": [ordinary, ordinary]},
            {**valid, "included_record_ids": ["RECORD-" + "F" * 32]},
            {**valid, "included_completion_ids": ["evt-not-in-candidates"]},
            {**valid, "source_digest": "garbage"},
            {**valid, "audience": "unauthorized"},
            {k: v for k, v in valid.items() if k != "source_record_ids"},
        ):
            with self.subTest(bad=bad):
                self.assertEqual(self.call("POST", url, bad)[0], 400)
        files = list((self.root / "work_archive" / "summary_events").glob("*.json"))
        self.assertEqual(len(files), 1)
        event = {"version": 1, "event_id": "forged-reselection-0001",
                 "summary_id": summary_id, "action": "reselect",
                 "actor": "chatgpt", "timestamp": STAMP, "base_revision": 1,
                 "changes": {k: v for k, v in valid.items()
                             if k not in {"revision", "confirmed_reselect"}}}
        with self.assertRaises(ValueError):
            app.validate_work_archive_event(event, "summary")

    def test_reselect_rejects_late_source_edits_even_if_id_list_unchanged(self):
        ordinary, important = self.create_facts()
        summary_id, preview = self._save_report(record_id=important)
        report_url = "/api/work-archive/summaries/" + summary_id + "/reselect"
        edit_url = "/api/work-records/" + ordinary + "/update"
        self.assertEqual(self.call("POST", edit_url, {
            "revision": 1, "content": "内容已被另一台设备修订"})[0], 200)
        # Candidate IDs are identical but digest must reveal this content revision.
        self.assertEqual(self.call("POST", report_url,
            self._reselect_payload(1, preview, included=[important]))[0], 409)
        self.assertEqual(len(list((self.root / "work_archive" /
                                   "summary_events").glob("*.json"))), 1)
        _, fresh = self.call("GET", "/api/work-archive/preview?period=daily&day=2026-11-09")
        self.assertEqual(fresh["source_record_ids"], preview["source_record_ids"])
        self.assertNotEqual(fresh["source_digest"], preview["source_digest"])
        self.assertEqual(self.call("POST", report_url,
            self._reselect_payload(1, fresh, included=[important]))[0], 200)

    def test_legacy_summary_can_be_explicitly_reselected_without_rewriting_legacy_event(self):
        ordinary, _ = self.create_facts()
        summary_id = "SUMMARY-" + "D" * 32
        root = {"version": 1, "event_id": "legacy-create-reselection",
                "summary_id": summary_id, "action": "create", "actor": "user",
                "timestamp": STAMP, "base_revision": 0,
                "changes": {"period": "daily", "period_start": "2026-11-09",
                            "period_end": "2026-11-09", "project_id": None,
                            "body": "旧版总结", "confirmed": True,
                            "source_record_ids": [ordinary],
                            "source_completion_ids": []}}
        app.append_work_archive_event(self.root, "summary", root)
        original = next((self.root / "work_archive" / "summary_events").glob("*.json"))
        original_bytes = original.read_bytes()
        _, preview = self.call("GET", "/api/work-archive/preview?period=daily&day=2026-11-09")
        self.assertEqual(self.call("POST",
            "/api/work-archive/summaries/" + summary_id + "/reselect",
            self._reselect_payload(1, preview, included=[ordinary]))[0], 200)
        self.assertEqual(original.read_bytes(), original_bytes)
        _, state = self.call("GET", "/api/work-archive")
        self.assertEqual(state["summaries"][0]["revision"], 2)
        self.assertEqual(state["summaries"][0]["included_record_ids"], [ordinary])
        self.assertFalse(state["summaries"][0]["confirmed"])

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
