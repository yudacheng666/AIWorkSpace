"""Independent-data tests for the first AIWorkSpace task loop."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as app_module  # noqa: E402
from app import (append_event, append_project_event, append_step_event, handler_factory,
                 read_workspace, validate_event, validate_project_event,
                 validate_step_event)  # noqa: E402


def event(event_id="demo-event-001", task_id="TASK-DEMO-001", action="create",
          revision=0, changes=None, actor="chatgpt", **other):
    return {"version": 1, "event_id": event_id, "task_id": task_id,
            "action": action, "actor": actor, "base_revision": revision,
            "timestamp": "2026-10-27T00:00:00Z",
            "changes": changes or {"title": "虚构测试任务", "status": "todo"}, **other}


def project_event(event_id="project-event-001", project_id="PROJECT-" + "A" * 32,
                  action="create", revision=0, name="虚构项目", actor="user"):
    return {"version": 1, "event_id": event_id, "project_id": project_id,
            "action": action, "actor": actor, "base_revision": revision,
            "timestamp": "2026-10-27T00:00:00Z", "changes": {"name": name}}


def step_event(event_id="step-event-001", task_id="TASK-DEMO-001",
               step_id="STEP-" + "A" * 32, action="create", revision=0,
               changes=None, actor="chatgpt", **other):
    return {"version": 1, "event_id": event_id, "task_id": task_id,
            "step_id": step_id, "action": action, "actor": actor,
            "base_revision": revision, "timestamp": "2026-10-30T00:00:00Z",
            "changes": changes or {"title": "虚构执行步骤"}, **other}


def step_order_event(event_id="step-order-001", task_id="TASK-DEMO-001",
                     revision=0, step_ids=None):
    return {"version": 1, "event_id": event_id, "task_id": task_id,
            "action": "reorder", "actor": "user",
            "base_revision": revision, "timestamp": "2026-10-30T00:00:00Z",
            "changes": {"step_ids": step_ids or ["STEP-" + "A" * 32]}}


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty(self):
        self.assertEqual(read_workspace(self.data_dir), {"tasks": [], "projects": [], "warnings": []})

    def test_chatgpt_creation_survives_reload(self):
        append_event(self.data_dir, event())
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["revision"], 1)

    def test_legacy_task_has_safe_management_defaults(self):
        append_event(self.data_dir, event())
        state = read_workspace(self.data_dir)["tasks"][0]
        self.assertIsNone(state["owner"])
        self.assertEqual(state["priority"], "normal")
        for field in ("due_date", "planned_date", "follow_up_date"):
            self.assertIsNone(state[field])
        persisted = next((self.data_dir / "events").glob("*.json")).read_text("utf-8")
        self.assertNotIn("follow_up_date", persisted)

    def test_external_task_event_three_dates_are_independent(self):
        append_event(self.data_dir, event(changes={
            "title": "虚构跟进事项", "status": "todo",
            "owner": "采购员甲", "priority": "high",
            "due_date": "2026-11-16",
            "planned_date": "2026-11-03",
            "follow_up_date": "2026-11-08"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["owner"], "采购员甲")
        self.assertEqual(task["priority"], "high")
        self.assertEqual((task["due_date"], task["planned_date"],
                          task["follow_up_date"]),
                         ("2026-11-16", "2026-11-03", "2026-11-08"))

    def test_metadata_conflict_uses_candidates_and_freezes_only_task(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event(
            "meta-conflict-one", action="update", revision=1,
            changes={"due_date": "2026-11-12", "priority": "high"}))
        append_event(self.data_dir, event(
            "meta-conflict-two", action="update", revision=1,
            changes={"due_date": "2026-11-14", "priority": "normal"}))
        append_event(self.data_dir, event(
            "other-independent", "TASK-OTHER", changes={"title": "独立任务"}))
        tasks = {t["task_id"]: t for t in read_workspace(self.data_dir)["tasks"]}
        self.assertTrue(tasks["TASK-DEMO-001"]["conflict"])
        self.assertEqual(tasks["TASK-DEMO-001"]["conflict_fields"],
                         ["due_date", "priority"])
        self.assertEqual(len(tasks["TASK-DEMO-001"]["conflict_candidates"]), 2)
        self.assertFalse(tasks["TASK-OTHER"]["conflict"])

    def test_management_event_validation_rejects_invalid_calendar_and_owner(self):
        bad_changes = [
            {"owner": " "}, {"owner": 99}, {"owner": "A" * 101},
            {"priority": "critical"}, {"priority": None},
            {"due_date": "2026-02-30"},
            {"planned_date": "2026-2-3"},
            {"follow_up_date": "2026-13-01"},
            {"follow_up_date": 20261102},
            {"planned_date": "2026-W40-1"}
        ]
        for changes in bad_changes:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_event(event(changes={"title": "虚构任务", **changes}))

    def test_numbered_steps_have_stable_ids_status_and_append_only_order(self):
        append_event(self.data_dir, event())
        first_id = "STEP-" + "A" * 32
        second_id = "STEP-" + "B" * 32
        append_step_event(self.data_dir, step_event(
            "step-create-001", step_id=first_id, changes={"title": "第一步"}))
        append_step_event(self.data_dir, step_event(
            "step-create-002", step_id=second_id, changes={"title": "第二步"}))
        append_step_event(self.data_dir, step_event(
            "step-update-001", step_id=first_id, action="update", revision=1,
            changes={"status": "doing", "title": "第一步已调整"}))
        append_step_event(self.data_dir, step_order_event(
            "step-order-002", revision=0, step_ids=[second_id, first_id]))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual([step["step_id"] for step in task["steps"]],
                         [second_id, first_id])
        self.assertEqual([step["position"] for step in task["steps"]], [1, 2])
        first = next(step for step in task["steps"] if step["step_id"] == first_id)
        self.assertEqual(first["title"], "第一步已调整")
        self.assertEqual(first["status"], "doing")
        self.assertEqual(first["revision"], 2)
        self.assertEqual(task["step_order_revision"], 1)
        files = list((self.data_dir / "step_events").glob("*.json"))
        self.assertEqual(len(files), 4)

    def test_legacy_tasks_default_to_no_steps_without_rewriting_history(self):
        append_event(self.data_dir, event())
        original = next((self.data_dir / "events").glob("*.json")).read_bytes()
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["steps"], [])
        self.assertEqual(task["step_order_revision"], 0)
        self.assertFalse(task["step_order_conflict"])
        self.assertEqual(next((self.data_dir / "events").glob("*.json")).read_bytes(), original)

    def test_step_conflict_freezes_only_the_affected_step(self):
        append_event(self.data_dir, event())
        append_step_event(self.data_dir, step_event(
            "step-conflict-create", step_id="STEP-" + "C" * 32,
            changes={"title": "冲突步骤"}))
        append_step_event(self.data_dir, step_event(
            "step-safe-create", step_id="STEP-" + "D" * 32,
            changes={"title": "正常步骤"}))
        append_step_event(self.data_dir, step_event(
            "step-conflict-a", step_id="STEP-" + "C" * 32, action="update",
            revision=1, changes={"title": "候选甲"}))
        append_step_event(self.data_dir, step_event(
            "step-conflict-b", step_id="STEP-" + "C" * 32, action="update",
            revision=1, changes={"title": "候选乙"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertFalse(task["conflict"])
        steps = {step["step_id"]: step for step in task["steps"]}
        self.assertTrue(steps["STEP-" + "C" * 32]["conflict"])
        self.assertEqual(len(steps["STEP-" + "C" * 32]["conflict_candidates"]), 2)
        self.assertFalse(steps["STEP-" + "D" * 32]["conflict"])

    def test_step_order_conflict_does_not_freeze_task_or_step_contents(self):
        append_event(self.data_dir, event())
        ids = ["STEP-" + "E" * 32, "STEP-" + "F" * 32]
        for index, step_id in enumerate(ids):
            append_step_event(self.data_dir, step_event(
                f"step-order-create-{index}", step_id=step_id,
                changes={"title": f"步骤{index + 1}"}))
        append_step_event(self.data_dir, step_order_event(
            "step-order-conflict-a", revision=0, step_ids=ids))
        append_step_event(self.data_dir, step_order_event(
            "step-order-conflict-b", revision=0, step_ids=list(reversed(ids))))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertFalse(task["conflict"])
        self.assertTrue(task["step_order_conflict"])
        self.assertEqual(len(task["steps"]), 2)
        self.assertFalse(any(step["conflict"] for step in task["steps"]))

    def test_step_events_wait_for_parent_task_sync(self):
        self.data_dir.mkdir(exist_ok=True)
        append_step_event(self.data_dir, step_event(
            "orphan-step-create", task_id="TASK-LATE-PARENT",
            step_id="STEP-" + "1" * 32))
        state = read_workspace(self.data_dir)
        self.assertEqual(state["tasks"], [])
        self.assertTrue(any("waiting for the parent task" in item for item in state["warnings"]))
        append_event(self.data_dir, event(
            "late-parent-create", task_id="TASK-LATE-PARENT",
            changes={"title": "父任务稍后同步"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["steps"][0]["step_id"], "STEP-" + "1" * 32)

    def test_duplicate_step_event_id_with_different_content_freezes_step(self):
        append_event(self.data_dir, event())
        step_id = "STEP-" + "2" * 32
        original = step_event("step-duplicate-id", step_id=step_id,
                              changes={"title": "原始步骤"})
        append_step_event(self.data_dir, original)
        conflicting = step_event("step-duplicate-id", step_id=step_id,
                                 changes={"title": "被篡改步骤"})
        (self.data_dir / "step_events" / "z_duplicate.json").write_text(
            json.dumps(conflicting), encoding="utf-8")
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(task["steps"][0]["conflict"])
        self.assertIn("event_id", task["steps"][0]["conflict_fields"])

    def test_step_event_validation_rejects_invalid_values(self):
        invalid = [
            step_event(step_id="STEP-invalid"),
            step_event(changes={"title": ""}),
            step_event(changes={"title": "x" * 201}),
            step_event(changes={"status": "done"}),
            step_event(action="create", revision=1),
            step_event(action="update", revision=0),
            step_event(changes={"unknown": True}),
            step_order_event(step_ids=["STEP-" + "A" * 32, "STEP-" + "A" * 32]),
            step_order_event(actor="chatgpt") if False else None,
        ]
        invalid = [item for item in invalid if item is not None]
        for item in invalid:
            with self.subTest(event=item), self.assertRaises(ValueError):
                validate_step_event(item)
        unconfirmed = step_event(
            "step-done-unconfirmed", step_id="STEP-" + "3" * 32,
            action="update", revision=1, changes={"status": "done"}, actor="user")
        with self.assertRaises(ValueError):
            validate_step_event(unconfirmed)
        confirmed_by_ai = step_event(
            "step-done-ai", step_id="STEP-" + "3" * 32,
            action="update", revision=1, changes={"status": "done"},
            confirmed_done=True)
        with self.assertRaises(ValueError):
            validate_step_event(confirmed_by_ai)

    def test_utf8_bom_event_from_external_writer_is_readable(self):
        events = self.data_dir / "events"
        events.mkdir()
        payload = json.dumps(event(
            "external-bom-event",
            task_id="TASK-EXTERNAL-BOM",
            changes={"title": "外部写入的虚构测试任务", "status": "todo"},
        ), ensure_ascii=False, indent=2)
        (events / "evt_external-bom-event.json").write_text(
            payload, encoding="utf-8-sig"
        )
        state = read_workspace(self.data_dir)
        self.assertEqual(state["warnings"], [])
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0]["task_id"], "TASK-EXTERNAL-BOM")
        self.assertEqual(state["tasks"][0]["title"], "外部写入的虚构测试任务")
        self.assertEqual(state["tasks"][0]["status"], "todo")

    def test_project_create_and_rename_are_append_only(self):
        original = append_project_event(self.data_dir, project_event())
        original_bytes = original.read_bytes()
        append_project_event(self.data_dir, project_event(
            "project-event-002", action="update", revision=1, name="改名后的虚构项目"
        ))
        state = read_workspace(self.data_dir)
        self.assertEqual(len(state["projects"]), 1)
        self.assertEqual(state["projects"][0]["name"], "改名后的虚构项目")
        self.assertEqual(state["projects"][0]["revision"], 2)
        self.assertFalse(state["projects"][0]["conflict"])
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(len(list((self.data_dir / "project_events").glob("*.json"))), 2)

    def test_task_project_links_are_read_and_legacy_events_default_to_inbox(self):
        project_id = "PROJECT-" + "B" * 32
        append_project_event(self.data_dir, project_event(
            project_id=project_id, name="项目甲"
        ))
        append_event(self.data_dir, event(
            changes={"title": "归属项目的任务", "status": "todo",
                     "project_id": project_id, "related_project_ids": []}
        ))
        append_event(self.data_dir, event(
            "demo-event-002", "TASK-DEMO-002",
            changes={"title": "旧格式任务", "status": "todo"}
        ))
        state = read_workspace(self.data_dir)
        tasks = {task["task_id"]: task for task in state["tasks"]}
        self.assertEqual(tasks["TASK-DEMO-001"]["project_id"], project_id)
        self.assertEqual(tasks["TASK-DEMO-001"]["project_name"], "项目甲")
        self.assertEqual(tasks["TASK-DEMO-002"]["project_id"], None)
        self.assertEqual(tasks["TASK-DEMO-002"]["related_project_ids"], [])
        self.assertEqual(state["warnings"], [])

    def test_task_with_missing_project_is_visible_with_warning(self):
        project_id = "PROJECT-" + "C" * 32
        append_event(self.data_dir, event(
            changes={"title": "项目事件尚未同步的任务", "status": "todo",
                     "project_id": project_id}
        ))
        state = read_workspace(self.data_dir)
        self.assertEqual(len(state["tasks"]), 1)
        self.assertTrue(state["tasks"][0]["project_missing"])
        self.assertTrue(any("referenced project" in warning for warning in state["warnings"]))

    def test_project_event_validation_rejects_invalid_name_and_revision(self):
        invalid = project_event(name=" " )
        with self.assertRaises(ValueError):
            validate_project_event(invalid)
        invalid = project_event(action="update", revision=0)
        with self.assertRaises(ValueError):
            validate_project_event(invalid)

    def test_user_edit_preserves_original(self):
        original = append_event(self.data_dir, event())
        original_bytes = original.read_bytes()
        append_event(self.data_dir, event("demo-event-002", action="update", revision=1,
                                           actor="user", changes={"title": "调整后的虚构任务", "status": "doing"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual((task["title"], task["status"], task["revision"]),
                         ("调整后的虚构任务", "doing", 2))
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)

    def test_completion_requires_real_user_confirmation(self):
        append_event(self.data_dir, event())
        changed = event("demo-event-003", action="update", revision=1,
                        changes={"status": "done"})
        with self.assertRaises(ValueError):
            validate_event(changed)
        changed["actor"] = "user"
        with self.assertRaises(ValueError):
            validate_event(changed)
        changed["confirmed_done"] = True
        append_event(self.data_dir, changed)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "done")

    def test_related_project_list_conflict_freezes_only_affected_task(self):
        """Two valid updates with different lists must not crash whole workspace."""
        linked = "PROJECT-" + "A" * 32
        append_project_event(self.data_dir, project_event(project_id=linked))
        append_event(self.data_dir, event(changes={
            "title": "含关联项目的任务", "status": "todo",
            "related_project_ids": []
        }))
        append_event(self.data_dir, event(
            "independent-001", "TASK-INDEPENDENT", changes={"title": "独立任务"}
        ))
        append_event(self.data_dir, event(
            "related-update-001", action="update", revision=1,
            changes={"related_project_ids": []}
        ))
        append_event(self.data_dir, event(
            "related-update-002", action="update", revision=1,
            changes={"related_project_ids": [linked]}
        ))
        state = read_workspace(self.data_dir)
        tasks = {task["task_id"]: task for task in state["tasks"]}
        self.assertEqual(len(tasks), 2)
        self.assertTrue(tasks["TASK-DEMO-001"]["conflict"])
        self.assertEqual(tasks["TASK-DEMO-001"]["conflict_fields"], ["related_project_ids"])
        self.assertEqual({tuple(c["changes"]["related_project_ids"])
                          for c in tasks["TASK-DEMO-001"]["conflict_candidates"]},
                         {(), (linked,)})
        self.assertFalse(tasks["TASK-INDEPENDENT"]["conflict"])
        self.assertEqual(tasks["TASK-INDEPENDENT"]["title"], "独立任务")

    def test_duplicate_event_id_different_related_lists_freezes_but_does_not_crash(self):
        append_event(self.data_dir, event())
        first = event("list-duplicate-001", action="update", revision=1,
                      changes={"related_project_ids": []})
        second = event("list-duplicate-001", action="update", revision=1,
                       changes={"related_project_ids": ["PROJECT-" + "C" * 32]})
        append_event(self.data_dir, first)
        (self.data_dir / "events" / "second_duplicate.json").write_text(
            json.dumps(second, ensure_ascii=False), encoding="utf-8"
        )
        state = read_workspace(self.data_dir)
        self.assertTrue(state["tasks"][0]["conflict"])
        self.assertIn("related_project_ids", state["tasks"][0]["conflict_fields"])

    def test_concurrent_same_revision_stops_without_winner(self):
        append_event(self.data_dir, event())
        for number, title in ((2, "AI 建议"), (3, "网页决定")):
            append_event(self.data_dir, event(f"demo-event-00{number}", action="update",
                                               revision=1, actor="user",
                                               changes={"title": title}))
        state = read_workspace(self.data_dir)
        self.assertTrue(state["tasks"][0]["conflict"])
        self.assertEqual(state["tasks"][0]["title"], "虚构测试任务")
        self.assertEqual(state["tasks"][0]["revision"], 1)
        self.assertEqual(state["tasks"][0]["conflict_fields"], ["title"])
        self.assertEqual(len(state["tasks"][0]["conflict_candidates"]), 2)
        self.assertTrue(any("conflicting" in message for message in state["warnings"]))

    def test_conflicting_status_values_are_explicitly_exposed(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-006", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        append_event(self.data_dir, event("demo-event-007", action="update", revision=1,
                                           actor="chatgpt", changes={"status": "blocked"}))
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(task["conflict"])
        self.assertEqual(task["status"], "todo")  # base state only; UI must not present it as resolved
        self.assertEqual(task["conflict_fields"], ["status"])
        self.assertEqual(
            {candidate["changes"]["status"] for candidate in task["conflict_candidates"]},
            {"doing", "blocked"},
        )

    def test_late_create_file_is_reconstructed_in_correct_order(self):
        append_event(self.data_dir, event("demo-event-004", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 0)
        append_event(self.data_dir, event())
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "doing")

    def test_corrupted_file_is_reported(self):
        (self.data_dir / "events").mkdir()
        (self.data_dir / "events" / "broken.json").write_text("{not valid json}", encoding="utf-8")
        self.assertTrue(read_workspace(self.data_dir)["warnings"])

    def test_duplicate_event_id_is_reported(self):
        append_event(self.data_dir, event())
        (self.data_dir / "events" / "duplicate.json").write_text(json.dumps(event()), encoding="utf-8")
        state = read_workspace(self.data_dir)
        self.assertEqual(len(state["tasks"]), 1)
        self.assertTrue(any("duplicate" in w for w in state["warnings"]))

    def test_concurrent_same_event_id_never_overwrites_existing_event(self):
        first = event("demo-event-099", changes={"title": "并发写入甲", "status": "todo"})
        second = event("demo-event-099", changes={"title": "并发写入乙", "status": "todo"})
        barrier = threading.Barrier(2)
        original_link = app_module.os.link
        outcomes = []
        outcomes_lock = threading.Lock()

        def synchronized_link(source, destination):
            # Force both writers to reach the atomic publication point together.
            barrier.wait(timeout=3)
            return original_link(source, destination)

        def writer(value):
            try:
                path = append_event(self.data_dir, value)
                result = ("success", json.loads(path.read_text(encoding="utf-8"))["changes"]["title"])
            except Exception as exc:  # capture thread result for assertions in the main thread
                result = ("error", type(exc).__name__)
            with outcomes_lock:
                outcomes.append(result)

        with patch("app.os.link", side_effect=synchronized_link):
            threads = [threading.Thread(target=writer, args=(value,)) for value in (first, second)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "writer thread hung")
        self.assertEqual(sum(result[0] == "success" for result in outcomes), 1, outcomes)
        self.assertEqual(sum(result == ("error", "FileExistsError") for result in outcomes), 1, outcomes)
        files = list((self.data_dir / "events").glob("evt_demo-event-099.json"))
        self.assertEqual(len(files), 1)
        stored = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertIn(stored["changes"]["title"], {"并发写入甲", "并发写入乙"})

    def test_duplicate_event_id_with_different_content_freezes_task(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-008", action="update", revision=1,
                                           changes={"status": "doing"}))
        conflicting = event("demo-event-008", action="update", revision=1,
                            changes={"status": "blocked"})
        (self.data_dir / "events" / "z_duplicate.json").write_text(
            json.dumps(conflicting), encoding="utf-8"
        )
        state = read_workspace(self.data_dir)
        task = state["tasks"][0]
        self.assertTrue(task["conflict"])
        self.assertEqual(task["conflict_fields"], ["status"])
        self.assertEqual(
            {candidate["changes"]["status"] for candidate in task["conflict_candidates"]},
            {"doing", "blocked"},
        )
        self.assertTrue(any("conflicting content" in warning for warning in state["warnings"]))

    def test_duplicate_event_id_across_tasks_freezes_both_tasks(self):
        append_event(self.data_dir, event())
        append_event(self.data_dir, event("demo-event-009", task_id="TASK-DEMO-002",
                                          changes={"title": "第二个虚构任务", "status": "todo"}))
        append_event(self.data_dir, event("demo-event-010", task_id="TASK-DEMO-001",
                                          action="update", revision=1,
                                          changes={"status": "doing"}))
        conflicting = event("demo-event-010", task_id="TASK-DEMO-002",
                            action="update", revision=1, changes={"status": "blocked"})
        (self.data_dir / "events" / "z_cross_task_duplicate.json").write_text(
            json.dumps(conflicting), encoding="utf-8"
        )
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertTrue(tasks["TASK-DEMO-001"]["conflict"])
        self.assertTrue(tasks["TASK-DEMO-002"]["conflict"])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        append_event(self.data_dir, event())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def create_project(self, body):
        request = Request(self.base + "/api/projects",
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def request(self, body):
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update",
                          data=json.dumps(body).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def create_task(self, body, extra_headers=None, content_type="application/json"):
        headers = {"Content-Type": content_type}
        headers.update(extra_headers or {})
        request = Request(self.base + "/api/tasks",
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def create_step(self, task_id="TASK-DEMO-001", title="虚构执行步骤", extra_headers=None):
        headers = {"Content-Type": "application/json"}
        headers.update(extra_headers or {})
        request = Request(self.base + f"/api/tasks/{task_id}/steps",
                          data=json.dumps({"title": title}, ensure_ascii=False).encode("utf-8"),
                          method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def update_step(self, step_id, body, task_id="TASK-DEMO-001", extra_headers=None):
        headers = {"Content-Type": "application/json"}
        headers.update(extra_headers or {})
        request = Request(self.base + f"/api/tasks/{task_id}/steps/{step_id}/update",
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def reorder_steps(self, step_ids, revision, task_id="TASK-DEMO-001", extra_headers=None):
        headers = {"Content-Type": "application/json"}
        headers.update(extra_headers or {})
        request = Request(self.base + f"/api/tasks/{task_id}/steps/reorder",
                          data=json.dumps({"step_ids": step_ids, "revision": revision}).encode("utf-8"),
                          method="POST", headers=headers)
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_get_survives_related_project_list_conflict(self):
        append_event(self.data_dir, event(
            "related-api-001", action="update", revision=1,
            changes={"related_project_ids": []}))
        append_event(self.data_dir, event(
            "related-api-002", action="update", revision=1,
            changes={"related_project_ids": ["PROJECT-" + "D" * 32]}))
        with urlopen(self.base + "/api/tasks", timeout=3) as reply:
            self.assertEqual(reply.status, 200)
            state = json.load(reply)
        self.assertEqual(len(state["tasks"]), 1)
        self.assertTrue(state["tasks"][0]["conflict"])
        self.assertIn("related_project_ids", state["tasks"][0]["conflict_fields"])
        code, _ = self.request({"title": "不能覆盖冲突任务",
                                "status": "todo", "revision": 1})
        self.assertEqual(code, 409)

    def test_title_edit_retains_unsynced_primary_and_related_ids(self):
        primary = "PROJECT-" + "D" * 32
        related = "PROJECT-" + "E" * 32
        append_event(self.data_dir, event(
            "missing-ref-create", task_id="TASK-MISSING-REF", changes={
                "title": "尚未同步项目的任务", "status": "todo",
                "project_id": primary, "related_project_ids": [related]}))
        original = [p.read_bytes() for p in (self.data_dir / "events").glob("*.json")]
        request = Request(
            self.base + "/api/tasks/TASK-MISSING-REF/update",
            data=json.dumps({"title": "只编辑标题", "status": "todo",
                             "revision": 1}, ensure_ascii=False).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
        task = next(t for t in read_workspace(self.data_dir)["tasks"]
                    if t["task_id"] == "TASK-MISSING-REF")
        self.assertEqual(task["project_id"], primary)
        self.assertEqual(task["related_project_ids"], [related])
        self.assertEqual(task["title"], "只编辑标题")
        self.assertEqual(task["revision"], 2)
        events = [json.loads(p.read_text("utf-8")) for p in
                  (self.data_dir / "events").glob("*.json")
                  if json.loads(p.read_text("utf-8"))["task_id"] == "TASK-MISSING-REF"]
        edited = next(e for e in events if e["action"] == "update")
        self.assertNotIn("project_id", edited["changes"])
        self.assertNotIn("related_project_ids", edited["changes"])
        # Existing JSON events are immutable.
        self.assertTrue(all(b in [p.read_bytes() for p in
                                   (self.data_dir / "events").glob("*.json")]
                            for b in original))

    def test_existing_unsynced_refs_can_survive_explicit_unchanged_payload(self):
        primary = "PROJECT-" + "C" * 32
        related = "PROJECT-" + "D" * 32
        append_event(self.data_dir, event("missing-unchanged", "TASK-PRESERVE",
            changes={"title": "待同步", "status": "todo",
                     "project_id": primary, "related_project_ids": [related]}))
        request = Request(
            self.base + "/api/tasks/TASK-PRESERVE/update",
            data=json.dumps({"title": "名称变更", "status": "doing", "revision": 1,
                             "project_id": primary,
                             "related_project_ids": [related]}, ensure_ascii=False).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
        task = next(t for t in read_workspace(self.data_dir)["tasks"]
                    if t["task_id"] == "TASK-PRESERVE")
        self.assertEqual(task["project_id"], primary)
        self.assertEqual(task["related_project_ids"], [related])

    def test_update_rejects_new_unsynced_project_reference(self):
        status, payload = self.create_task({"title": "正常任务"})
        self.assertEqual(status, 201)
        request = Request(
            self.base + "/api/tasks/" + payload["task_id"] + "/update",
            data=json.dumps({"title": "异常绑定", "status": "todo", "revision": 1,
                             "project_id": "PROJECT-" + "F" * 32}).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 400)
        task = next(t for t in read_workspace(self.data_dir)["tasks"]
                    if t["task_id"] == payload["task_id"])
        self.assertIsNone(task["project_id"])

    def test_create_task_with_all_m3_2_fields_and_append_only_history(self):
        payload = {"title": "跟进事项", "owner": "  员工甲  ", "priority": "urgent",
                   "due_date": "2026-11-20", "planned_date": "2026-11-01",
                   "follow_up_date": "2026-11-07"}
        status, created = self.create_task(payload)
        self.assertEqual(status, 201)
        task = next(t for t in read_workspace(self.data_dir)["tasks"]
                    if t["task_id"] == created["task_id"])
        self.assertEqual(task["owner"], "员工甲")
        self.assertEqual(task["priority"], "urgent")
        for field in ("due_date", "planned_date", "follow_up_date"):
            self.assertEqual(task[field], payload[field])
        self.assertEqual(task["revision"], 1)
        written = next(json.loads(p.read_text("utf-8"))
                       for p in (self.data_dir / "events").glob("*.json")
                       if created["task_id"] in p.read_text("utf-8"))
        self.assertEqual(written["changes"]["owner"], "员工甲")
        self.assertEqual(written["changes"]["follow_up_date"], "2026-11-07")

    def test_update_only_follow_up_date_preserves_other_dates_and_project_refs(self):
        primary = "PROJECT-" + "A" * 32
        related = "PROJECT-" + "B" * 32
        append_event(self.data_dir, event(
            "old-extra-task", "TASK-M3-02", changes={
                "title": "跟进虚构项目", "status": "todo",
                "project_id": primary, "related_project_ids": [related],
                "due_date": "2026-12-15", "planned_date": "2026-11-02",
                "follow_up_date": "2026-11-05"}))
        events = self.data_dir / "events"
        original = {p.name: p.read_bytes() for p in events.glob("*.json")}
        request = Request(
            self.base + "/api/tasks/TASK-M3-02/update",
            data=json.dumps({"title": "跟进虚构项目", "status": "todo",
                             "revision": 1, "follow_up_date": "2026-11-12"}).encode(),
            method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as reply:
            self.assertEqual(reply.status, 200)
        task = next(t for t in read_workspace(self.data_dir)["tasks"]
                    if t["task_id"] == "TASK-M3-02")
        self.assertEqual(task["follow_up_date"], "2026-11-12")
        self.assertEqual(task["due_date"], "2026-12-15")
        self.assertEqual(task["planned_date"], "2026-11-02")
        self.assertEqual(task["project_id"], primary)
        self.assertEqual(task["related_project_ids"], [related])
        new_events = [json.loads(p.read_text("utf-8")) for p in events.glob("*.json")
                      if p.name not in original]
        self.assertEqual(len(new_events), 1)
        self.assertNotIn("project_id", new_events[0]["changes"])
        self.assertNotIn("related_project_ids", new_events[0]["changes"])
        self.assertNotIn("due_date", new_events[0]["changes"])
        self.assertNotIn("planned_date", new_events[0]["changes"])
        self.assertEqual(new_events[0]["changes"]["follow_up_date"], "2026-11-12")
        self.assertEqual({name: (events / name).read_bytes() for name in original}, original)

    def test_clear_owner_and_date_without_touching_priority(self):
        self.assertEqual(self.request({"title": "虚构测试任务", "status": "todo",
                                      "revision": 1, "owner": "员工乙",
                                      "priority": "high", "due_date": "2026-11-05"})[0], 200)
        status, _ = self.request({"title": "虚构测试任务", "status": "todo",
                                  "revision": 2, "owner": None, "due_date": None})
        self.assertEqual(status, 200)
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertIsNone(task["owner"])
        self.assertIsNone(task["due_date"])
        self.assertEqual(task["priority"], "high")

    def test_invalid_m3_2_fields_rejected_without_event_writes(self):
        bad_fields = [
            {"priority": "blocker"}, {"owner": 123}, {"owner": "x" * 101},
            {"due_date": "2026-02-30"}, {"due_date": "2026-01-1"},
            {"follow_up_date": "tomorrow"}, {"planned_date": "2026-00-10"},
            {"planned_date": {"year": 2026}}, {"follow_up_date": 17}
        ]
        for changes in bad_fields:
            with self.subTest(fields=changes):
                original = len(list((self.data_dir / "events").glob("*.json")))
                code, _ = self.create_task({"title": "不应新增", **changes})
                self.assertEqual(code, 400)
                code, _ = self.request({"title": "虚构测试任务", "status": "todo",
                                        "revision": 1, **changes})
                self.assertEqual(code, 400)
                self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), original)

    def test_stale_metadata_revision_rejected_without_overwriting_new_date(self):
        status, _ = self.request({"title": "虚构测试任务", "status": "todo",
                                  "revision": 1, "due_date": "2026-11-10"})
        self.assertEqual(status, 200)
        code, _ = self.request({"title": "虚构测试任务", "status": "todo",
                                "revision": 1, "due_date": "2026-11-15"})
        self.assertEqual(code, 409)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["due_date"], "2026-11-10")

    def test_create_task_success_and_persists(self):
        status, result = self.create_task({"title": "  新任务：安排资料整理  "})
        self.assertEqual(status, 201)
        self.assertTrue(result["saved"])
        self.assertEqual(result["revision"], 1)
        self.assertRegex(result["task_id"], r"^TASK-[A-F0-9]{32}$")
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual(tasks[result["task_id"]]["title"], "新任务：安排资料整理")
        self.assertEqual(tasks[result["task_id"]]["status"], "todo")
        self.assertEqual(tasks[result["task_id"]]["revision"], 1)
        self.assertFalse(tasks[result["task_id"]]["conflict"])
        created = [json.loads(p.read_text(encoding="utf-8"))
                   for p in (self.data_dir / "events").glob("*.json")
                   if json.loads(p.read_text(encoding="utf-8"))["task_id"] == result["task_id"]]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["action"], "create")
        self.assertEqual(created[0]["actor"], "user")
        self.assertEqual(created[0]["base_revision"], 0)
        self.assertEqual(created[0]["changes"], {"title": "新任务：安排资料整理",
                                                  "status": "todo"})
        with urlopen(self.base + "/api/tasks", timeout=3) as reply:
            self.assertIn(result["task_id"], {t["task_id"] for t in json.load(reply)["tasks"]})

    def test_create_rejects_invalid_payload_without_writing(self):
        invalid = [{"title": ""}, {"title": "   "}, {"title": "x" * 201},
                   {"title": 123}, {"title": "valid", "status": "done"},
                   {"title": "valid", "task_id": "TASK-INJECTED"},
                   {"title": "valid", "actor": "chatgpt"},
                   {"title": "valid", "base_revision": 1}]
        before = len(list((self.data_dir / "events").glob("*.json")))
        for payload in invalid:
            with self.subTest(payload=payload):
                status, _ = self.create_task(payload)
                self.assertEqual(status, 400)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), before)

    def test_create_rejects_untrusted_origin_and_host(self):
        before = len(list((self.data_dir / "events").glob("*.json")))
        for headers in ({"Origin": "https://untrusted.example"},
                        {"Host": "attacker.example"}):
            with self.subTest(headers=headers):
                status, response = self.create_task({"title": "never saved"}, headers)
                self.assertEqual(status, 403)
                self.assertIn("local requests only", response["error"])
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), before)

    def test_create_requires_json_content_type(self):
        status, _ = self.create_task({"title": "wrong mime"}, content_type="text/plain")
        self.assertEqual(status, 415)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)

    def test_create_handles_disk_publish_failure_without_phantom_task(self):
        with patch("app.os.link", side_effect=OSError("simulated write failure")):
            status, response = self.create_task({"title": "will not persist"})
        self.assertEqual(status, 500)
        self.assertEqual(response["error"], "unable to save event")
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 1)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)

    def test_create_concurrent_requests_get_distinct_ids(self):
        results = []
        lock = threading.Lock()

        def writer(value):
            result = self.create_task({"title": value})
            with lock:
                results.append(result)

        first = threading.Thread(target=writer, args=("Task one",))
        second = threading.Thread(target=writer, args=("Task two",))
        first.start()
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual([code for code, _ in results].count(201), 2, results)
        task_ids = [result["task_id"] for _, result in results]
        self.assertEqual(len(set(task_ids)), 2)
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual({tasks[tid]["title"] for tid in task_ids}, {"Task one", "Task two"})

    def test_project_create_assign_and_related_project_links(self):
        status_a, project_a = self.create_project({"name": "虚构项目甲"})
        status_b, project_b = self.create_project({"name": "虚构项目乙"})
        self.assertEqual(status_a, 201)
        self.assertEqual(status_b, 201)
        self.assertRegex(project_a["project_id"], r"^PROJECT-[A-F0-9]{32}$")
        status, result = self.create_task({
            "title": "归属项目的虚构任务",
            "project_id": project_a["project_id"],
            "related_project_ids": [project_b["project_id"]],
        })
        self.assertEqual(status, 201)
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        task = tasks[result["task_id"]]
        self.assertEqual(task["project_id"], project_a["project_id"])
        self.assertEqual(task["project_name"], "虚构项目甲")
        self.assertEqual(task["related_project_ids"], [project_b["project_id"]])
        self.assertEqual(task["related_project_names"], ["虚构项目乙"])

    def test_project_rename_and_stale_revision_protection(self):
        status, project = self.create_project({"name": "待重命名项目"})
        self.assertEqual(status, 201)
        request = Request(
            self.base + f"/api/projects/{project['project_id']}/update",
            data=json.dumps({"name": "新项目名称", "revision": 1}, ensure_ascii=False).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
        stale = Request(
            self.base + f"/api/projects/{project['project_id']}/update",
            data=json.dumps({"name": "过期项目名称", "revision": 1}, ensure_ascii=False).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(stale, timeout=3)
        self.assertEqual(raised.exception.code, 409)
        saved = read_workspace(self.data_dir)["projects"][0]
        self.assertEqual(saved["name"], "新项目名称")
        self.assertEqual(saved["revision"], 2)

    def test_task_create_rejects_unknown_project_reference(self):
        status, _ = self.create_task({
            "title": "不应保存",
            "project_id": "PROJECT-" + "F" * 32,
        })
        self.assertEqual(status, 400)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)

    def test_duplicate_project_name_is_rejected(self):
        self.assertEqual(self.create_project({"name": "重复项目"})[0], 201)
        self.assertEqual(self.create_project({"name": "重复项目"})[0], 409)

    def test_step_create_update_and_reorder_end_to_end(self):
        first_status, first = self.create_step(title="第一步")
        second_status, second = self.create_step(title="第二步")
        self.assertEqual((first_status, second_status), (201, 201))
        self.assertRegex(first["step_id"], r"^STEP-[A-F0-9]{32}$")
        self.assertNotEqual(first["step_id"], second["step_id"])
        code, result = self.update_step(first["step_id"], {
            "title": "第一步已修改", "status": "doing", "revision": 1})
        self.assertEqual(code, 200)
        self.assertEqual(result["revision"], 2)
        code, reordered = self.reorder_steps([second["step_id"], first["step_id"]], 0)
        self.assertEqual(code, 200)
        self.assertEqual(reordered["revision"], 1)
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual([step["step_id"] for step in task["steps"]],
                         [second["step_id"], first["step_id"]])
        saved = next(step for step in task["steps"] if step["step_id"] == first["step_id"])
        self.assertEqual((saved["title"], saved["status"], saved["revision"]),
                         ("第一步已修改", "doing", 2))
        self.assertEqual(len(list((self.data_dir / "step_events").glob("*.json"))), 4)

    def test_step_completion_requires_explicit_user_confirmation(self):
        _, created = self.create_step()
        code, _ = self.update_step(created["step_id"], {"status": "done", "revision": 1})
        self.assertEqual(code, 400)
        code, _ = self.update_step(created["step_id"], {
            "status": "done", "revision": 1, "confirmed_done": True})
        self.assertEqual(code, 200)
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["steps"][0]["status"], "done")
        saved_event = next(json.loads(path.read_text("utf-8"))
                           for path in (self.data_dir / "step_events").glob("*.json")
                           if json.loads(path.read_text("utf-8"))["action"] == "update")
        self.assertEqual(saved_event["actor"], "user")
        self.assertIs(saved_event["confirmed_done"], True)

    def test_step_stale_revision_and_conflict_protection(self):
        _, created = self.create_step()
        sid = created["step_id"]
        self.assertEqual(self.update_step(sid, {"status": "doing", "revision": 1})[0], 200)
        self.assertEqual(self.update_step(sid, {"status": "blocked", "revision": 1})[0], 409)
        self.assertEqual(self.update_step(sid, {"title": "合法新步骤", "revision": 2})[0], 200)
        append_step_event(self.data_dir, step_event(
            "step-server-conflict-a", step_id=sid, action="update", revision=3,
            changes={"title": "冲突候选甲"}))
        append_step_event(self.data_dir, step_event(
            "step-server-conflict-b", step_id=sid, action="update", revision=3,
            changes={"title": "冲突候选乙"}))
        self.assertEqual(self.update_step(sid, {"title": "不应覆盖", "revision": 3})[0], 409)
        other_status, other = self.create_step(title="独立正常步骤")
        self.assertEqual(other_status, 201)
        self.assertEqual(self.update_step(other["step_id"], {
            "status": "doing", "revision": 1})[0], 200)

    def test_step_order_requires_exact_membership_and_revision(self):
        first = self.create_step(title="步骤甲")[1]["step_id"]
        second = self.create_step(title="步骤乙")[1]["step_id"]
        before = len(list((self.data_dir / "step_events").glob("*.json")))
        self.assertEqual(self.reorder_steps([first], 0)[0], 400)
        self.assertEqual(len(list((self.data_dir / "step_events").glob("*.json"))), before)
        self.assertEqual(self.reorder_steps([second, first], 0)[0], 200)
        self.assertEqual(self.reorder_steps([first, second], 0)[0], 409)
        self.assertEqual([step["step_id"] for step in read_workspace(self.data_dir)["tasks"][0]["steps"]],
                         [second, first])

    def test_step_order_conflict_blocks_reorder_but_not_step_content_edit(self):
        first = self.create_step(title="步骤甲")[1]["step_id"]
        second = self.create_step(title="步骤乙")[1]["step_id"]
        append_step_event(self.data_dir, step_order_event(
            "step-order-server-a", revision=0, step_ids=[first, second]))
        append_step_event(self.data_dir, step_order_event(
            "step-order-server-b", revision=0, step_ids=[second, first]))
        state = read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(state["step_order_conflict"])
        self.assertEqual(self.reorder_steps([first, second], 0)[0], 409)
        self.assertEqual(self.update_step(first, {"status": "doing", "revision": 1})[0], 200)

    def test_step_create_rejects_untrusted_host_and_disk_failure(self):
        before = len(list((self.data_dir / "step_events").glob("*.json")))
        status, response = self.create_step(extra_headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        self.assertIn("local requests only", response["error"])
        with patch("app.os.link", side_effect=OSError("simulated step write failure")):
            status, response = self.create_step(title="不会落盘")
        self.assertEqual(status, 500)
        self.assertEqual(response["error"], "unable to save event")
        self.assertEqual(len(list((self.data_dir / "step_events").glob("*.json"))), before)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["steps"], [])

    def test_step_write_is_blocked_when_parent_task_has_conflict(self):
        append_event(self.data_dir, event(
            "step-parent-conflict-a", action="update", revision=1,
            changes={"title": "候选甲"}))
        append_event(self.data_dir, event(
            "step-parent-conflict-b", action="update", revision=1,
            changes={"title": "候选乙"}))
        before = len(list((self.data_dir / "step_events").glob("*.json")))
        status, _ = self.create_step()
        self.assertEqual(status, 409)
        self.assertEqual(len(list((self.data_dir / "step_events").glob("*.json"))), before)

    def test_webpage_and_api_available(self):
        with urlopen(self.base + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertIn("AIWorkSpace", html)
            self.assertIn("新建任务", html)
            self.assertIn("项目管理", html)
            self.assertIn('id="create-project"', html)
            self.assertIn('id="create-task"', html)
            self.assertIn("状态存在冲突（未裁决）", html)
            self.assertIn("冲突候选不是最终结论", html)
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            self.assertEqual(json.load(response)["tasks"][0]["title"], "虚构测试任务")

    def test_get_rejects_untrusted_host_headers(self):
        port = self.server.server_port
        for host in ("attacker.example", f"127.0.0.1:{port}.attacker.example",
                     f"localhost.attacker.example:{port}"):
            with self.subTest(host=host):
                request = Request(self.base + "/api/tasks", headers={"Host": host})
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=3)
                self.assertEqual(raised.exception.code, 403)
                self.assertIn("local requests only", raised.exception.read().decode("utf-8"))

    def test_localhost_host_header_is_allowed(self):
        host = f"localhost:{self.server.server_port}"
        request = Request(self.base + "/api/tasks", headers={"Host": host})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["tasks"][0]["title"], "虚构测试任务")

    def test_post_rejects_untrusted_host_header(self):
        body = json.dumps({"title": "不应保存", "status": "doing", "revision": 1}).encode("utf-8")
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update", data=body,
                          method="POST", headers={"Content-Type": "application/json",
                                                  "Host": "attacker.example"})
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 403)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")

    def test_http_save_then_read(self):
        status, result = self.request({"title": "网页更新", "status": "doing", "revision": 1})
        self.assertEqual(status, 200)
        self.assertTrue(result["saved"])
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            self.assertEqual(json.load(response)["tasks"][0]["title"], "网页更新")

    def test_stale_revision_cannot_overwrite(self):
        self.request({"title": "第一次", "status": "doing", "revision": 1})
        status, _ = self.request({"title": "过期写入", "status": "blocked", "revision": 1})
        self.assertEqual(status, 409)

    def test_api_rejects_write_when_task_has_unresolved_conflict(self):
        append_event(self.data_dir, event("demo-event-011", action="update", revision=1,
                                           actor="user", changes={"status": "doing"}))
        append_event(self.data_dir, event("demo-event-012", action="update", revision=1,
                                           actor="chatgpt", changes={"status": "blocked"}))
        before = len(list((self.data_dir / "events").glob("*.json")))
        status, _ = self.request({"title": "不应写入", "status": "todo", "revision": 1})
        after = len(list((self.data_dir / "events").glob("*.json")))
        self.assertEqual(status, 409)
        self.assertEqual(after, before)

    def test_web_cannot_complete_without_confirmation(self):
        status, _ = self.request({"title": "虚构测试任务", "status": "done", "revision": 1})
        self.assertEqual(status, 400)
        status, _ = self.request({"title": "虚构测试任务", "status": "done",
                                  "revision": 1, "confirmed_done": True})
        self.assertEqual(status, 200)

    def test_user_can_edit_title_after_completion(self):
        status, _ = self.request({"title": "虚构测试任务", "status": "done",
                                  "revision": 1, "confirmed_done": True})
        self.assertEqual(status, 200)
        status, _ = self.request({"title": "已完成事项的备注调整", "status": "done",
                                  "revision": 2, "confirmed_done": True})
        self.assertEqual(status, 200)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "已完成事项的备注调整")

    def test_external_origin_cannot_update(self):
        request = Request(self.base + "/api/tasks/TASK-DEMO-001/update",
                          data=json.dumps({"title": "被拒绝", "status": "doing", "revision": 1}).encode(),
                          method="POST", headers={"Content-Type": "application/json",
                                                  "Origin": "https://untrusted.example"})
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 403)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], "虚构测试任务")

    def test_synced_chatgpt_event_becomes_visible_without_restart(self):
        second = event("demo-event-005", "TASK-DEMO-002", changes={"title": "第二个虚构事项"})
        append_event(self.data_dir, second)
        with urlopen(self.base + "/api/tasks", timeout=3) as response:
            tasks = json.load(response)["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[1]["title"], "第二个虚构事项")


if __name__ == "__main__":
    unittest.main()
