"""Two-device Drive-sync fault injection using isolated synthetic event folders.

These tests model eventual file delivery only. They do not claim to exercise the
Google Drive service or a user's production devices.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import app


RECORD = "RECORD-" + "F" * 32
TASK = "TASK-WORK-TEST-001"


def work_event(event_id: str, action: str, base_revision: int,
               changes: dict) -> dict:
    return {
        "version": 1,
        "event_id": event_id,
        "record_id": RECORD,
        "action": action,
        "actor": "user",
        "timestamp": "2026-11-11T08:00:00Z",
        "base_revision": base_revision,
        "changes": changes,
    }


def object_detail_event(event_id: str, base_revision: int,
                        description: str) -> dict:
    return {
        "version": 1,
        "event_id": event_id,
        "object_type": "task",
        "object_id": TASK,
        "action": "set",
        "actor": "user",
        "timestamp": "2026-11-11T08:00:00Z",
        "base_revision": base_revision,
        "changes": {"description": description},
    }


class TwoDeviceSyncFaultInjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def device(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def deliver(self, source: Path, target: Path, folder: str,
                event_id: str, filename: str | None = None) -> Path:
        source_file = source / folder / f"evt_{event_id}.json"
        target_dir = target / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / (filename or source_file.name)
        target_file.write_bytes(source_file.read_bytes())
        return target_file

    def test_work_record_recovers_after_creation_and_predecessor_arrive_late(self):
        """A replica must freeze an incomplete chain, then recover when gaps arrive."""
        device_a = self.device("device-a")
        device_b = self.device("device-b")
        folder = "work_archive/record_events"
        root = work_event("sync-record-create-0001", "create", 0, {
            "content": "评估是否采用方案 A",
            "occurred_on": "2026-11-11",
            "record_type": "decision",
            "outcome": "暂不采用",
        })
        revision_1 = work_event("sync-record-update-0001", "update", 1, {
            "occurred_on": "2026-11-12",
        })
        revision_2 = work_event("sync-record-update-0002", "update", 2, {
            "featured": True,
        })
        for event in (root, revision_1, revision_2):
            app.append_work_record_event(device_a, event)

        original_bytes = {
            path.name: path.read_bytes()
            for path in (device_a / folder).glob("*.json")
        }

        # Device B receives the newest update first, while creation and revision 1
        # are still offline on device A.
        self.deliver(device_a, device_b, folder, revision_2["event_id"])
        partial = app.read_work_records(device_b)
        self.assertEqual(partial["records"], [])
        self.assertTrue(any(RECORD in warning for warning in partial["warnings"]))

        # The creation file arrives, but the missing predecessor still prevents
        # revision 2 from being applied or presented as current data.
        self.deliver(device_a, device_b, folder, root["event_id"])
        waiting = app.read_work_records(device_b)
        self.assertEqual(len(waiting["records"]), 1)
        self.assertTrue(waiting["records"][0]["conflict"])
        self.assertEqual(waiting["records"][0]["revision"], 1)
        self.assertEqual(waiting["records"][0]["outcome"], "暂不采用")
        self.assertFalse(waiting["records"][0]["featured"])

        # Once the missing predecessor arrives, the contiguous chain is rebuilt
        # deterministically without choosing by timestamps or rewriting events.
        self.deliver(device_a, device_b, folder, revision_1["event_id"])
        recovered = app.read_work_records(device_b)
        record = recovered["records"][0]
        self.assertFalse(record["conflict"])
        self.assertEqual(record["revision"], 3)
        self.assertEqual(record["occurred_on"], "2026-11-12")
        self.assertTrue(record["featured"])
        self.assertEqual(record["content"], "评估是否采用方案 A")
        self.assertEqual(record["outcome"], "暂不采用")
        self.assertEqual(
            original_bytes,
            {path.name: path.read_bytes() for path in (device_a / folder).glob("*.json")},
        )

    def test_object_description_recovers_after_out_of_order_file_delivery(self):
        """A late predecessor may resolve a temporary gap, never a timestamp winner."""
        device_a = self.device("device-a")
        device_b = self.device("device-b")
        folder = "work_archive/object_detail_events"
        first = object_detail_event(
            "sync-object-detail-0001", 0, "初始任务说明")
        second = object_detail_event(
            "sync-object-detail-0002", 1, "修订后的任务说明")
        app.append_object_detail_event(device_a, first)
        app.append_object_detail_event(device_a, second)
        original_bytes = {
            path.name: path.read_bytes()
            for path in (device_a / folder).glob("*.json")
        }

        self.deliver(device_a, device_b, folder, second["event_id"])
        partial = app.read_object_details(device_b)["objects"][("task", None, TASK)]
        self.assertTrue(partial["conflict"])
        self.assertEqual(partial["revision"], 0)
        self.assertEqual(partial["description"], "")

        self.deliver(device_a, device_b, folder, first["event_id"])
        recovered = app.read_object_details(device_b)["objects"][("task", None, TASK)]
        self.assertFalse(recovered["conflict"])
        self.assertEqual(recovered["revision"], 2)
        self.assertEqual(recovered["description"], "修订后的任务说明")
        self.assertEqual(
            original_bytes,
            {path.name: path.read_bytes() for path in (device_a / folder).glob("*.json")},
        )

    def test_concurrent_edits_from_two_devices_freeze_only_the_shared_object(self):
        """Two edits based on the same revision must not be resolved by arrival time."""
        device_a = self.device("device-a")
        device_b = self.device("device-b")
        merged = self.device("merged-drive-view")
        folder = "work_archive/object_detail_events"
        root = object_detail_event("sync-object-root-0001", 0, "共同的初始说明")
        app.append_object_detail_event(device_a, root)
        self.deliver(device_a, device_b, folder, root["event_id"])

        edit_a = object_detail_event("sync-object-device-a-0001", 1, "设备 A 的说明")
        edit_b = object_detail_event("sync-object-device-b-0001", 1, "设备 B 的说明")
        app.append_object_detail_event(device_a, edit_a)
        app.append_object_detail_event(device_b, edit_b)

        # The merged view receives A's file and then B's file. Reversing this
        # delivery order must not change the reducer's conflict result.
        self.deliver(device_a, merged, folder, root["event_id"])
        self.deliver(device_a, merged, folder, edit_a["event_id"])
        self.deliver(device_b, merged, folder, edit_b["event_id"])
        state = app.read_object_details(merged)
        detail = state["objects"][("task", None, TASK)]
        self.assertTrue(detail["conflict"])
        self.assertEqual(detail["revision"], 1)
        self.assertEqual(detail["description"], "共同的初始说明")
        self.assertTrue(any("concurrent object description edits" in warning
                            for warning in state["warnings"]))

    def test_identical_duplicate_delivery_is_idempotent_for_both_event_streams(self):
        """A byte-identical duplicate is ignored rather than inflating a revision."""
        device_a = self.device("device-a")
        device_b = self.device("device-b")
        record_folder = "work_archive/record_events"
        detail_folder = "work_archive/object_detail_events"
        record = work_event("sync-duplicate-record-0001", "create", 0, {
            "content": "一条测试工作记录",
            "occurred_on": "2026-11-11",
        })
        detail = object_detail_event(
            "sync-duplicate-detail-0001", 0, "一条测试说明")
        app.append_work_record_event(device_a, record)
        app.append_object_detail_event(device_a, detail)
        self.deliver(device_a, device_b, record_folder, record["event_id"])
        self.deliver(device_a, device_b, detail_folder, detail["event_id"])

        self.deliver(device_a, device_b, record_folder, record["event_id"],
                     filename="duplicate-copy.json")
        self.deliver(device_a, device_b, detail_folder, detail["event_id"],
                     filename="duplicate-copy.json")

        records = app.read_work_records(device_b)
        self.assertEqual(len(records["records"]), 1)
        self.assertFalse(records["records"][0]["conflict"])
        self.assertEqual(records["records"][0]["revision"], 1)
        self.assertTrue(any("identical work record event duplicated" in warning
                            for warning in records["warnings"]))

        details = app.read_object_details(device_b)
        detail_state = details["objects"][("task", None, TASK)]
        self.assertFalse(detail_state["conflict"])
        self.assertEqual(detail_state["revision"], 1)
        self.assertEqual(detail_state["description"], "一条测试说明")
        self.assertTrue(any("identical object detail event duplicated" in warning
                            for warning in details["warnings"]))

    def test_legacy_client_cannot_overwrite_decision_content_or_outcome(self):
        """An older client event without record_type must still fail closed."""
        device_a = self.device("device-a")
        device_b = self.device("device-b")
        folder = "work_archive/record_events"
        decision = work_event("sync-legacy-decision-root", "create", 0, {
            "content": "评估是否向供应商转卖零件",
            "occurred_on": "2026-11-11",
            "record_type": "decision",
            "outcome": "不卖",
        })
        app.append_work_record_event(device_a, decision)
        self.deliver(device_a, device_b, folder, decision["event_id"])

        # Older releases do not send the newer record_type field. Their ordinary
        # update envelope is still syntactically valid, so the reducer—not only
        # the HTTP validator—must protect the immutable decision.
        legacy_update = work_event("sync-legacy-decision-edit", "update", 1, {
            "content": "旧客户端尝试覆盖决策背景",
            "outcome": "卖",
        })
        app.append_work_record_event(device_b, legacy_update)
        state = app.read_work_records(device_b)
        record = state["records"][0]
        self.assertTrue(record["conflict"])
        self.assertEqual(record["revision"], 1)
        self.assertEqual(record["content"], "评估是否向供应商转卖零件")
        self.assertEqual(record["outcome"], "不卖")


if __name__ == "__main__":
    unittest.main()
