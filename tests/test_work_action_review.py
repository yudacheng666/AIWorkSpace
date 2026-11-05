"""AI-assisted work action review: only human confirmation writes task or record events.

No network models or real company files; every test creates synthetic isolated
events and runs against the production local HTTP handler.
"""
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

RECORD = "RECORD-" + "A" * 32
PROJECT = "PROJECT-" + "B" * 32
TASK = "TASK-EXISTING-ACTION-TEST"
STAMP = "2026-11-05T09:00:00Z"


def proposal(title: str, day: str | None = None, revision: int = 1) -> dict:
    return {"version": 1, "record_id": RECORD, "record_revision": revision,
            "proposals": [{"title": title, "due_date": day}]}


class ActionSchemaTests(unittest.TestCase):
    def test_reject_action_injection_unknown_fields_and_bad_calendar(self):
        good = proposal("核实虚构设备交期", "2026-11-12")
        self.assertEqual(app.validate_action_proposal_list(good), good)
        bads = [
            good | {"actor": "chatgpt"},
            good | {"version": True},
            good | {"record_revision": True},
            good | {"record_revision": 0},
            good | {"record_id": "RECORD-INVALID"},
            good | {"proposals": [{"title": "核实交期", "due_date": "2026-02-30"}]},
            good | {"proposals": [{"title": "已完成", "due_date": None, "status": "done"}]},
            good | {"proposals": [{"title": "", "due_date": None}]},
            good | {"proposals": []},
            good | {"proposals": [{"title": "同一任务", "due_date": None}] * 2},
            good | {"proposals": [{"title": "任务" + str(i), "due_date": None}
                                  for i in range(6)]},
        ]
        for item in bads:
            with self.subTest(item=item), self.assertRaises(ValueError):
                app.validate_action_proposal_list(item)
        base = {"version": 1, "event_id": "origin-task-create-0001",
                "task_id": TASK, "action": "create", "actor": "user",
                "timestamp": STAMP, "base_revision": 0,
                "changes": {"title": "虚构行动", "status": "todo",
                            "source_work_record": {"record_id": RECORD, "revision": 1}}}
        app.validate_event(base)
        for item in [
            {**base, "actor": "chatgpt"},
            {**base, "action": "update", "base_revision": 1},
            {**base, "changes": base["changes"] |
             {"source_work_record": {"record_id": RECORD, "revision": False}}},
            {**base, "changes": base["changes"] | {"status": "done"}},
        ]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                app.validate_event(item)

    def test_duplicate_similarity_is_advisory_not_a_model(self):
        workspace = {"tasks": [{"task_id": TASK, "title": "跟进虚构供应商报价",
                                "status": "doing", "project_id": PROJECT,
                                "conflict": False},
                               {"task_id": "TASK-OTHER-PROJECT", "title": "跟进虚构供应商报价",
                                "status": "todo", "project_id": None,
                                "conflict": False}]}
        identical = app.similar_action_tasks(" 跟进虚构 供应商报价 ", PROJECT, workspace)
        self.assertEqual(len(identical), 1)
        self.assertEqual(identical[0]["match_type"], "same_title")
        related = app.similar_action_tasks("继续跟进虚构供应商报价", PROJECT, workspace)
        self.assertEqual(related[0]["match_type"], "possibly_related")
        self.assertEqual(app.similar_action_tasks("完全不相关项目", PROJECT, workspace), [])


class ActionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiworkspace-action-test-")
        self.dir = Path(self.temp.name)
        app.append_project_event(self.dir, {
            "version": 1, "event_id": "actions-project-create-001", "project_id": PROJECT,
            "action": "create", "actor": "user", "timestamp": STAMP,
            "base_revision": 0, "changes": {"name": "虚构设备项目"}})
        app.append_event(self.dir, {
            "version": 1, "event_id": "actions-task-create-001", "task_id": TASK,
            "action": "create", "actor": "user", "timestamp": STAMP,
            "base_revision": 0,
            "changes": {"title": "跟进虚构供应商报价", "status": "todo",
                        "project_id": PROJECT}})
        app.append_work_record_event(self.dir, {
            "version": 1, "event_id": "actions-work-create-001",
            "record_id": RECORD, "action": "create", "actor": "user",
            "timestamp": STAMP, "base_revision": 0,
            "changes": {"content": "与供应商沟通，下一步需要进一步核对报价。",
                        "occurred_on": "2026-11-04", "project_id": PROJECT}})
        self.record_bytes = {p.name: p.read_bytes() for p in
                             (self.dir / "work_archive" / "record_events").glob("*.json")}
        self.task_bytes = {p.name: p.read_bytes() for p in
                           (self.dir / "events").glob("*.json")}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def call(self, method: str, path: str, payload=None, extra_headers=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(self.base + path, data=data, method=method,
                      headers={"Content-Type": "application/json", **(extra_headers or {})})
        try:
            with urlopen(req, timeout=7) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def confirm(self, title: str, *, reviewed: bool = False, revision: int = 1,
                due_date: str | None = None) -> dict:
        return {"record_id": RECORD, "record_revision": revision,
                "title": title, "due_date": due_date,
                "confirmed_create": True, "duplicate_reviewed": reviewed}

    def test_preview_is_read_only_and_no_task_auto_completed(self):
        code, preview = self.call("POST", "/api/work-archive/actions/preview",
                                  proposal("跟进虚构供应商报价"))
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["record_id"], RECORD)
        self.assertEqual(preview["record_revision"], 1)
        self.assertEqual(preview["proposals"][0]["matches"][0]["task_id"], TASK)
        self.assertEqual(preview["proposals"][0]["matches"][0]["match_type"], "same_title")
        self.assertEqual(self.record_bytes, {p.name: p.read_bytes() for p in
                                             (self.dir / "work_archive" / "record_events").glob("*.json")})
        self.assertEqual(self.task_bytes, {p.name: p.read_bytes() for p in
                                           (self.dir / "events").glob("*.json")})
        self.assertEqual(self.call("POST", "/api/work-archive/actions/preview",
                                   proposal("草稿", "2026-02-30"))[0], 400)
        self.assertEqual(self.call("POST", "/api/work-archive/actions/preview",
                                   proposal("草稿") | {"confirmed_done": True})[0], 400)
        self.assertEqual(self.call("POST", "/api/work-archive/actions/preview",
                                   proposal("草稿"), {"Origin": "https://unknown.example"})[0], 403)
        self.assertEqual(self.task_bytes, {p.name: p.read_bytes() for p in
                                           (self.dir / "events").glob("*.json")})

    def test_user_explicit_create_single_task_event_with_immutable_provenance(self):
        title = "安排虚构设备联调"
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create",
                                   self.confirm(title) | {"confirmed_create": False})[0], 400)
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create",
                                   self.confirm(title) | {"status": "done"})[0], 400)
        self.assertEqual(len(list((self.dir / "events").glob("*.json"))), 1)
        code, created = self.call("POST", "/api/work-archive/actions/create",
                                  self.confirm(title, due_date="2026-11-15"))
        self.assertEqual(code, 201, created)
        self.assertEqual(created["record_id"], RECORD)
        self.assertEqual(created["revision"], 1)
        task = next(t for t in app.read_workspace(self.dir)["tasks"]
                    if t["task_id"] == created["task_id"])
        self.assertEqual(task["status"], "todo")
        self.assertEqual(task["due_date"], "2026-11-15")
        self.assertEqual(task["project_id"], PROJECT)
        self.assertEqual(task["source_work_record"], {"record_id": RECORD, "revision": 1})
        self.assertEqual(len(list((self.dir / "events").glob("*.json"))), 2)
        self.assertEqual(self.task_bytes[TASK_EVENT], (self.dir / "events" / TASK_EVENT).read_bytes())
        self.assertEqual(self.record_bytes, {p.name: p.read_bytes() for p in
                                             (self.dir / "work_archive" / "record_events").glob("*.json")})
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create",
                                   self.confirm(title))[0], 409, "same source/title retry rejected")
        _, records = self.call("GET", "/api/work-records")
        source = next(x for x in records["records"] if x["record_id"] == RECORD)
        self.assertTrue(any(link["target_id"] == created["task_id"] and
                            link["relation"] == "derived_action"
                            for link in source["action_link_labels"]))
        self.assertEqual(app.read_workspace(self.dir)["tasks"][0]["status"], "todo")

    def test_possible_duplicate_must_be_reviewed_and_exact_title_blocked(self):
        exact = self.confirm("跟进虚构供应商报价", reviewed=True)
        code, result = self.call("POST", "/api/work-archive/actions/create", exact)
        self.assertEqual(code, 409, result)
        self.assertIn("same title", result["error"])
        likely = self.confirm("继续跟进虚构供应商报价")
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create", likely)[0], 409)
        code, created = self.call("POST", "/api/work-archive/actions/create",
                                  likely | {"duplicate_reviewed": True})
        self.assertEqual(code, 201, created)
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create",
                                   likely | {"duplicate_reviewed": True})[0], 409)
        self.assertEqual(len(list((self.dir / "events").glob("*.json"))), 2)

    def test_link_existing_only_appends_record_edit_and_stale_revision_blocks(self):
        payload = {"record_id": RECORD, "record_revision": 1,
                   "task_id": TASK, "confirmed_link": True}
        self.assertEqual(self.call("POST", "/api/work-archive/actions/link",
                                   payload | {"confirmed_link": False})[0], 400)
        code, first = self.call("POST", "/api/work-archive/actions/link", payload)
        self.assertEqual(code, 200, first)
        self.assertEqual(first["revision"], 2)
        self.assertEqual(self.call("POST", "/api/work-archive/actions/link", payload)[0], 409)
        code, second = self.call("POST", "/api/work-archive/actions/link",
                                 payload | {"record_revision": 2})
        self.assertEqual(code, 200, second)
        self.assertFalse(second["saved"])
        self.assertEqual(self.call("POST", "/api/work-archive/actions/create",
                                   self.confirm("新的联调", revision=1))[0], 409)
        self.assertEqual(self.task_bytes, {p.name: p.read_bytes() for p in
                                           (self.dir / "events").glob("*.json")})
        files = list((self.dir / "work_archive" / "record_events").glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertEqual(self.record_bytes[TASK_RECORD], (self.dir / "work_archive" /
                                                         "record_events" / TASK_RECORD).read_bytes())
        _, records = self.call("GET", "/api/work-records")
        r = records["records"][0]
        self.assertEqual(r["revision"], 2)
        self.assertEqual(r["action_links"][0]["relation"], "derived_action")


TASK_EVENT = "evt_actions-task-create-001.json"
TASK_RECORD = "evt_actions-work-create-001.json"

if __name__ == "__main__":
    unittest.main()
