"""Deterministic task/step conflict triage: synthetic data only.

No production Drive IDs, filenames, content or external network access.
"""
import json
import tempfile
import unittest
from pathlib import Path

from app import (
    append_event, append_step_event, list_data_reviews, read_workspace,
    validate_event, validate_step_event,
)

TASK_ID = "TASK-" + "A" * 32
STEP_ID = "STEP-" + "B" * 32


def task_event(number, action, base, changes, **metadata):
    event = {
        "version": 1, "event_id": "evt-synthetic-%04d" % number,
        "task_id": TASK_ID, "actor": "user",
        "action": action, "timestamp": "2026-11-05T10:%02d:00Z" % (number % 60),
        "base_revision": base, "changes": changes,
    }
    event.update(metadata)
    return event


def step_event(number, action, base, changes, **metadata):
    event = task_event(number, action, base, changes, **metadata)
    event["step_id"] = STEP_ID
    return event


def write_event(folder, event, filename=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (filename or (event["event_id"] + ".json"))
    path.write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
    return path


def root_event():
    return task_event(1, "create", 0, {"title": "虚构：材料整理", "status": "todo"})


def note_files(folder):
    return {p.name: p.read_bytes() for p in folder.rglob("*.json")}


class NotificationTriageTests(unittest.TestCase):
    def test_manual_conflict_remains_readable_and_non_actionable(self):
        workspace = {
            "tasks": [{
                "task_id": TASK_ID, "title": "虚构：材料整理", "revision": 4,
                "conflict": True, "conflict_fields": ["title"],
                "conflict_candidates": [
                    {"event_id": "evt-a", "actor": "user", "timestamp": "2026-11-05T10:00:00Z",
                     "changes": {"title": "虚构：甲"}},
                    {"event_id": "evt-b", "actor": "user", "timestamp": "2026-11-05T10:01:00Z",
                     "changes": {"title": "虚构：乙"}},
                ],
            }],
            "warnings": [f"{TASK_ID}: conflicting edits of revision 4"],
        }
        with tempfile.TemporaryDirectory() as temp:
            out = list_data_reviews(Path(temp), workspace)
            self.assertEqual(len(out["items"]), 1)
            item = out["items"][0]
            self.assertEqual(item["task_id"], TASK_ID)
            self.assertEqual(item["task_title"], "虚构：材料整理")
            self.assertTrue(item["concurrent_task_edit"])
            self.assertEqual(len(item["related_edits"]), 2)
            self.assertFalse(item["can_apply"])
            self.assertFalse(item["can_authorize"])
            self.assertIn("相同的旧版本", item["user_guidance"]["summary"])
            self.assertEqual(list(Path(temp).rglob("*.json")), [])

    def test_nonoverlap_updates_auto_merge_no_mutation_or_open_alarm(self):
        events = [
            root_event(),
            task_event(2, "update", 1, {"priority": "high"}),
            task_event(3, "update", 1, {"title": "虚构：新版资料", "due_date": "2026-11-05"}),
        ]
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            folder = data / "events"
            for event in events:
                write_event(folder, event)
            original = note_files(data)
            workspace = read_workspace(data)
            task = workspace["tasks"][0]
            self.assertFalse(task["conflict"], workspace["warnings"])
            self.assertEqual(task["revision"], 2, "siblings form one logical revision")
            self.assertEqual(task["title"], "虚构：新版资料")
            self.assertEqual(task["priority"], "high")
            self.assertEqual(task["due_date"], "2026-11-05")
            self.assertEqual(len(task["auto_merge_groups"]), 1)
            self.assertEqual(len(task["auto_merge_groups"][0]["event_ids"]), 2)
            self.assertRegex(task["merge_basis_required"], r"^[0-9a-f]{64}$")
            register = list_data_reviews(data)
            self.assertEqual(register["summary"]["open_count"], 0)
            self.assertEqual(register["summary"]["auto_merged"], 1)
            notice = register["items"][0]
            self.assertEqual(notice["category"], "auto_merged")
            self.assertEqual(notice["status"], "auto_merged")
            self.assertIn("优先级", notice["user_guidance"]["summary"])
            self.assertFalse(notice["can_apply"])
            self.assertEqual(note_files(data), original)
            self.assertFalse((data / "review_events").exists())

    def test_new_client_attests_merged_siblings_when_writing_next_event(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            for event in (root_event(),
                          task_event(2, "update", 1, {"priority": "high"}),
                          task_event(3, "update", 1, {"due_date": "2026-11-15"})):
                write_event(data / "events", event)
            event = task_event(4, "update", 2, {"title": "虚构：最新版"})
            append_event(data, event)
            self.assertRegex(event["merge_basis"], r"^[0-9a-f]{64}$")
            task = read_workspace(data)["tasks"][0]
            self.assertFalse(task["conflict"])
            self.assertEqual(task["revision"], 3)
            self.assertEqual(task["priority"], "high")
            self.assertEqual(task["title"], "虚构：最新版")

    def test_confirmed_lifecycle_after_verified_merge_is_not_regressed(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            for event in (root_event(),
                          task_event(2, "update", 1, {"priority": "high"}),
                          task_event(3, "update", 1, {"due_date": "2026-11-15"})):
                write_event(data / "events", event)
            lifecycle = task_event(
                4, "trash", 2, {"trashed_at": "2026-11-05T10:04:00Z"}
            )
            append_event(data, lifecycle)
            self.assertRegex(lifecycle["merge_basis"], r"^[0-9a-f]{64}$")
            result = read_workspace(data, include_trashed=True)
            task = result["tasks"][0]
            self.assertFalse(task["conflict"], result["warnings"])
            self.assertEqual(task["revision"], 3)
            self.assertTrue(task["trashed_at"])
            self.assertEqual(task["priority"], "high")

    def test_verified_delete_after_auto_merged_step_remains_legal(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            write_event(data / "events", root_event())
            for event in (
                step_event(10, "create", 0, {"title": "虚构：步骤", "position": 1}),
                step_event(11, "update", 1, {"title": "虚构：调整步骤"}),
                step_event(12, "update", 1, {"due_date": "2026-11-15"}),
            ):
                write_event(data / "step_events", event)
            deletion = step_event(
                13, "delete", 2, {"deleted_at": "2026-11-05T10:13:00Z"},
                confirmed_delete=True,
            )
            append_step_event(data, deletion)
            self.assertRegex(deletion["merge_basis"], r"^[0-9a-f]{64}$")
            result = read_workspace(data)
            self.assertFalse(result["tasks"][0]["conflict"])
            self.assertFalse(any("conflicting edits" in w for w in result["warnings"]))
            self.assertEqual(len(result["tasks"][0]["steps"]), 0)

    def test_old_client_late_write_without_merge_basis_is_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            for event in (root_event(),
                          task_event(2, "update", 1, {"priority": "high"}),
                          task_event(3, "update", 1, {"due_date": "2026-11-15"}),
                          task_event(4, "update", 2, {"title": "虚构：未同步完就改标题"})):
                write_event(data / "events", event)
            task = read_workspace(data)["tasks"][0]
            self.assertTrue(task["conflict"])
            self.assertEqual(task["revision"], 2)
            self.assertTrue(any("lacks matching merge basis" in w
                                for w in read_workspace(data)["warnings"]))
            self.assertFalse(any(x["category"] == "auto_merged"
                                 for x in list_data_reviews(data)["items"]))

    def test_late_third_sibling_revokes_old_merge_basis_safely(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            for event in (root_event(), task_event(2, "update", 1, {"priority": "high"}),
                          task_event(3, "update", 1, {"due_date": "2026-11-15"})):
                write_event(data / "events", event)
            event = task_event(4, "update", 2, {"title": "虚构：最终版"})
            append_event(data, event)
            write_event(data / "events", task_event(5, "update", 1, {"owner": "虚构负责人"}))
            state = read_workspace(data)
            self.assertTrue(state["tasks"][0]["conflict"])
            self.assertEqual(state["tasks"][0]["revision"], 2)
            self.assertEqual(state["tasks"][0]["owner"], "虚构负责人")
            self.assertTrue(any("lacks matching merge basis" in w
                                for w in state["warnings"]))

    def test_same_field_different_values_stays_blocked_despite_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            for event in (root_event(),
                          task_event(2, "update", 1, {"title": "虚构：甲"}),
                          task_event(59, "update", 1, {"title": "虚构：乙"})):
                write_event(data / "events", event)
            task = read_workspace(data)["tasks"][0]
            self.assertTrue(task["conflict"])
            self.assertEqual(task["title"], "虚构：材料整理")
            self.assertEqual(task["revision"], 1)
            self.assertEqual(len(task["conflict_candidates"]), 2)
            self.assertEqual(list_data_reviews(data)["summary"]["open_count"], 1)

    def test_status_and_lifecycle_edits_never_merge_automatically(self):
        cases = [
            task_event(3, "update", 1, {"status": "doing"}),
            task_event(3, "update", 1, {"status": "done"}, confirmed_done=True),
            task_event(3, "trash", 1, {"trashed_at": "2026-11-05T10:03:00Z"}),
        ]
        for danger in cases:
            with self.subTest(action=danger["action"], changes=danger["changes"]):
                with tempfile.TemporaryDirectory() as temp:
                    data = Path(temp)
                    for event in (root_event(), task_event(2, "update", 1, {"priority": "high"}), danger):
                        write_event(data / "events", event)
                    self.assertTrue(read_workspace(data)["tasks"][0]["conflict"])
                    self.assertFalse(read_workspace(data)["tasks"][0]["auto_merge_groups"])

    def test_duplicate_event_id_variants_freeze_even_disjoint_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            a = task_event(2, "update", 1, {"title": "虚构：新标题"})
            b = task_event(2, "update", 1, {"priority": "high"})
            for i, event in enumerate((root_event(), a, b)):
                write_event(data / "events", event, f"evt_{i}.json")
            task = read_workspace(data)["tasks"][0]
            self.assertTrue(task["conflict"])
            self.assertEqual(task["auto_merge_groups"], [])

    def test_timestamp_is_not_an_authority_and_order_is_deterministic(self):
        sequences = [(2, 3), (3, 2)]
        projected = []
        for sequence in sequences:
            with tempfile.TemporaryDirectory() as temp:
                data = Path(temp)
                write_event(data / "events", root_event(), "evt_0.json")
                entries = {
                    2: task_event(58, "update", 1, {"priority": "high"}),
                    3: task_event(2, "update", 1, {"due_date": "2026-11-15"}),
                }
                for i, key in enumerate(sequence):
                    write_event(data / "events", entries[key], "evt_branch_%d.json" % i)
                task = read_workspace(data)["tasks"][0]
                self.assertFalse(task["conflict"])
                projected.append((task["revision"], task["priority"], task["due_date"],
                                  task["merge_basis_required"]))
        self.assertEqual(projected[0], projected[1])

    def test_step_dates_and_title_auto_merge_with_attestation(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            write_event(data / "events", root_event())
            for event in (
                step_event(10, "create", 0, {"title": "虚构：步骤", "position": 1}),
                step_event(11, "update", 1, {"title": "虚构：改进步骤"}),
                step_event(12, "update", 1, {"due_date": "2026-11-15"}),
            ):
                write_event(data / "step_events", event)
            task = read_workspace(data)["tasks"][0]
            self.assertFalse(task["conflict"])
            step = task["steps"][0]
            self.assertFalse(step["conflict"])
            self.assertEqual(step["revision"], 2)
            self.assertEqual(step["title"], "虚构：改进步骤")
            self.assertEqual(step["due_date"], "2026-11-15")
            self.assertEqual(list_data_reviews(data)["summary"]["auto_merged"], 1)
            followup = step_event(13, "update", 2, {"status": "doing"})
            append_step_event(data, followup)
            self.assertRegex(followup["merge_basis"], r"^[0-9a-f]{64}$")
            latest = read_workspace(data)["tasks"][0]["steps"][0]
            self.assertFalse(latest["conflict"])
            self.assertEqual(latest["status"], "doing")

    def test_step_delete_or_completion_remains_manual_conflict(self):
        for unsafe in (
            step_event(12, "delete", 1, {"deleted_at": "2026-11-05T10:12:00Z"},
                       confirmed_delete=True),
            step_event(12, "update", 1, {"status": "done"}, confirmed_done=True),
        ):
            with self.subTest(action=unsafe["action"]):
                with tempfile.TemporaryDirectory() as temp:
                    data = Path(temp)
                    write_event(data / "events", root_event())
                    for event in (step_event(10, "create", 0, {"title": "虚构：步骤", "position": 1}),
                                  step_event(11, "update", 1, {"due_date": "2026-11-15"}),
                                  unsafe):
                        write_event(data / "step_events", event)
                    self.assertTrue(read_workspace(data)["tasks"][0]["steps"][0]["conflict"])

    def test_invalid_merge_basis_and_unknown_context_are_rejected(self):
        bad = task_event(4, "update", 2, {"priority": "urgent"}, merge_basis="not-a-hash")
        with self.assertRaisesRegex(ValueError, "merge basis"):
            validate_event(bad)
        bad_step = step_event(4, "update", 2, {"title": "虚构：步骤"}, merge_basis="bad")
        with self.assertRaisesRegex(ValueError, "merge basis"):
            validate_step_event(bad_step)

    def test_unrelated_warning_is_not_falsely_linked_to_a_task(self):
        with tempfile.TemporaryDirectory() as temp:
            out = list_data_reviews(
                Path(temp), {"tasks": [], "warnings": [
                    "Unknown data format; check synchronization before changes"
                ]})
            self.assertEqual(len(out["items"]), 1)
            item = out["items"][0]
            self.assertIsNone(item["task_id"])
            self.assertFalse(item["concurrent_task_edit"])
            self.assertEqual(item["related_edits"], [])


if __name__ == "__main__":
    unittest.main()
