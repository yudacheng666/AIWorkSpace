"""Regression coverage for readable, read-only conflict notifications.

Synthetic event details only; production Google Drive files are never loaded.
"""
import json
import tempfile
import unittest
from pathlib import Path

from app import list_data_reviews


class NotificationTriageTests(unittest.TestCase):
    def test_concurrent_revision_warning_identifies_task_and_candidates(self):
        task_id = "TASK-" + "A" * 32
        workspace = {
            "tasks": [{
                "task_id": task_id,
                "title": "虚构：材料整理",
                "revision": 4,
                "conflict": True,
                "conflict_fields": ["priority", "title", "due_date"],
                "conflict_candidates": [
                    {"event_id": "evt-example-a", "actor": "user",
                     "timestamp": "2026-11-05T10:00:00Z",
                     "changes": {"priority": "high"}},
                    {"event_id": "evt-example-b", "actor": "user",
                     "timestamp": "2026-11-05T10:01:00Z",
                     "changes": {"title": "虚构：新版材料整理", "due_date": "2026-11-05"}},
                ],
            }],
            "warnings": [f"{task_id}: conflicting edits of revision 4"],
        }
        with tempfile.TemporaryDirectory() as temp:
            out = list_data_reviews(Path(temp), workspace)
            self.assertEqual(len(out["items"]), 1)
            item = out["items"][0]
            self.assertEqual(item["task_id"], task_id)
            self.assertEqual(item["task_title"], "虚构：材料整理")
            self.assertEqual(item["category"], "semantic_conflict")
            self.assertTrue(item["concurrent_task_edit"])
            self.assertEqual(len(item["related_edits"]), 2)
            self.assertFalse(item["can_apply"])
            self.assertFalse(item["can_authorize"])
            self.assertIn("相同的旧版本", item["user_guidance"]["summary"])
            self.assertIn("复制给 ChatGPT 核查", item["user_guidance"]["recommendation"])
            self.assertEqual(list(Path(temp).rglob("*.json")), [],
                             "listing notices must not write an event")

    def test_reducer_finds_two_valid_same_revision_edits_without_writing(self):
        task_id = "TASK-" + "B" * 32
        base = {
            "version": 1, "task_id": task_id, "actor": "user",
            "timestamp": "2026-11-05T10:00:00Z",
        }
        entries = [
            {**base, "event_id": "11111111-1111-4111-8111-111111111111",
             "action": "create", "base_revision": 0,
             "changes": {"title": "虚构：设计资料", "status": "todo"}},
            {**base, "event_id": "22222222-2222-4222-8222-222222222222",
             "action": "update", "base_revision": 1,
             "changes": {"priority": "high"}},
            {**base, "event_id": "33333333-3333-4333-8333-333333333333",
             "action": "update", "base_revision": 1,
             "changes": {"title": "虚构：资料归档", "due_date": "2026-11-05"}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "events"
            directory.mkdir()
            for i, event in enumerate(entries):
                (directory / f"evt_demo_{i}.json").write_text(
                    json.dumps(event, ensure_ascii=False), encoding="utf-8")
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            response = list_data_reviews(Path(temp))
            matched = [item for item in response["items"]
                       if item.get("task_id") == task_id
                       and item.get("concurrent_task_edit")]
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["task_title"], "虚构：设计资料")
            self.assertEqual(len(matched[0]["related_edits"]), 2)
            self.assertFalse(matched[0]["can_apply"])
            self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)
            self.assertFalse((Path(temp) / "review_events").exists())

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
