"""AI analysis handoff and featured-career-material source tests (synthetic only)."""
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

PROJECT = "PROJECT-" + "A" * 32
TASK = "TASK-FAKE-PERIOD-REPORT-001"
RECORD = "RECORD-" + "B" * 32
STAMP = "2026-11-05T03:00:00Z"


class WorkAnalysisContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        app.append_project_event(self.dir, {
            "version": 1, "event_id": "handoff-project-0001",
            "project_id": PROJECT, "action": "create",
            "actor": "user", "timestamp": STAMP, "base_revision": 0,
            "changes": {"name": "虚构项目"}
        })
        app.append_event(self.dir, {
            "version": 1, "event_id": "handoff-task-create-0001",
            "task_id": TASK, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"title": "虚构合同整理", "status": "todo", "project_id": PROJECT}
        })
        app.append_event(self.dir, {
            "version": 1, "event_id": "handoff-task-finished-0001",
            "task_id": TASK, "action": "update", "actor": "user",
            "timestamp": STAMP, "base_revision": 1, "confirmed_done": True,
            "changes": {"status": "done"}
        })
        app.append_work_record_event(self.dir, {
            "version": 1, "event_id": "handoff-record-create-0001",
            "record_id": RECORD, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"content": "虚构需求评审会议已经召开",
                        "outcome": "待核对资料接口",
                        "occurred_on": "2026-11-04", "project_id": PROJECT,
                        "duration_minutes": 25, "featured": True,
                        "evidence_links": [{
                            "title": "虚构评审记录",
                            "url": "https://drive.google.com/file/d/example/view"
                        }]}
        })
        self.original = self._hash_files()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), app.handler_factory(self.dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def _hash_files(self):
        return {p.relative_to(self.dir).as_posix(): p.read_bytes()
                for p in self.dir.rglob("*.json")}

    def call(self, path, headers=None):
        request = Request(self.base + path, headers=headers or {})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_summary_handoff_contains_exact_records_completions_and_evidence(self):
        path = "/api/work-archive/analysis-context?period=weekly&day=2026-11-05"
        code, result = self.call(path + "&project_id=" + PROJECT)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["period_start"], "2026-11-02")
        self.assertEqual(result["period_end"], "2026-11-08")
        self.assertEqual(result["source_record_ids"], [RECORD])
        self.assertEqual(result["source_completion_ids"],
                         ["handoff-task-finished-0001"])
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["completion_count"], 1)
        self.assertIn(RECORD, result["prompt"])
        self.assertIn("handoff-task-finished-0001", result["prompt"])
        self.assertIn("虚构需求评审会议", result["prompt"])
        self.assertIn("drive.google.com/file/d/example", result["prompt"])
        self.assertIn("不得将工作记录数量冒充完成任务数量", result["prompt"])
        self.assertIn("只为事实与引用资料", result["prompt"].replace("仅为", "只为"))
        self.assertEqual(self.original, self._hash_files(),
                         "read-only handoff must not produce events")

    def test_portfolio_contains_only_user_featured_and_never_guesses_kpis(self):
        code, result = self.call("/api/work-archive/portfolio-context?project_id=" + PROJECT)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["source_record_ids"], [RECORD])
        self.assertIn(RECORD, result["prompt"])
        self.assertIn("用户标记", result["prompt"])
        self.assertIn("不要编造产出金额", result["prompt"])
        self.assertIn("drive.google.com/file/d/example", result["prompt"])
        # Unfeatured records are not silently promoted to portfolio.
        app.append_work_record_event(self.dir, {
            "version": 1, "event_id": "handoff-record-nonfeatured",
            "record_id": "RECORD-" + "C" * 32,
            "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"content": "未经精选的另一个工作", "occurred_on": "2026-11-04"}
        })
        self.assertEqual(self.call("/api/work-archive/portfolio-context")[1][
            "source_record_ids"], [RECORD])

    def test_date_and_scope_validation_and_no_hidden_model_call(self):
        for path in (
            "/api/work-archive/analysis-context?period=weekly&day=2026-02-29",
            "/api/work-archive/analysis-context?period=quarterly&day=2026-11-05",
            "/api/work-archive/analysis-context?period=daily&day=2026-11-05&unexpected=1",
            "/api/work-archive/analysis-context?period=daily&day=2026-11-05&day=2026-11-04",
            "/api/work-archive/portfolio-context?project_id=bad",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.call(path)[0], 400)
        self.assertEqual(self.call(
            "/api/work-archive/analysis-context?period=daily&day=2026-11-05",
            headers={"Origin": "https://outside.example"})[0], 403)
        self.assertEqual(self.original, self._hash_files())

    def test_conflict_fail_closed_and_empty_featured_scopes(self):
        # Parallel edits of one revision block any export rather than skipping.
        for eid in ("handoff-concurrent-0001", "handoff-concurrent-0002"):
            app.append_work_record_event(self.dir, {
                "version": 1, "event_id": eid, "record_id": RECORD,
                "action": "update", "actor": "user",
                "timestamp": STAMP, "base_revision": 1,
                "changes": {"outcome": eid}
            })
        self.assertEqual(self.call(
            "/api/work-archive/analysis-context?period=weekly&day=2026-11-05")[0],
                         409)
        self.assertEqual(self.call("/api/work-archive/portfolio-context")[0], 409)

    def test_empty_portfolio_is_not_misrepresented_as_real_career_results(self):
        other = "PROJECT-" + "E" * 32
        app.append_project_event(self.dir, {
            "version": 1, "event_id": "handoff-other-project-0001",
            "project_id": other, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"name": "另一个虚构项目"}
        })
        self.assertEqual(self.call(
            "/api/work-archive/portfolio-context?project_id=" + other)[0], 409)


if __name__ == "__main__":
    unittest.main()
