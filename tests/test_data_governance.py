"""Synthetic end-to-end governance loop tests; never touch real user data."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


TASK_ID = "TASK-" + "A" * 32
STEP_ID = "STEP-" + "B" * 32


def task_event(event_id="governance-task-create-001", action="create", revision=0,
               changes=None, actor="user", **other):
    return {
        "version": 1, "event_id": event_id, "task_id": TASK_ID,
        "action": action, "actor": actor, "timestamp": "2026-11-03T04:00:00Z",
        "base_revision": revision,
        "changes": changes if changes is not None else {"title": "虚构治理测试任务", "status": "todo"},
        **other,
    }


def step_event(event_id="governance-step-create-001", action="create", revision=0,
               changes=None, **other):
    return {
        "version": 1, "event_id": event_id, "task_id": TASK_ID, "step_id": STEP_ID,
        "action": action, "actor": "user", "timestamp": "2026-11-03T04:01:00Z",
        "base_revision": revision,
        "changes": changes if changes is not None else {"title": "虚构步骤", "position": 1},
        **other,
    }


class DataGovernanceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiworkspace-governance-")
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"
        self.data_dir.mkdir()
        app.append_event(self.data_dir, task_event())
        app.append_step_event(self.data_dir, step_event())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.data_dir))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path, payload=None):
        request = Request(
            self.base + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"} if payload is not None else {},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def invalid_source(self, folder, filename, value):
        path = self.data_dir / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        path.write_bytes(raw)
        return path, raw

    def reviews(self):
        code, result = self.request("/api/reviews")
        self.assertEqual(code, 200)
        return result

    def item(self, category):
        matches = [entry for entry in self.reviews()["items"] if entry["category"] == category]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def authorize(self, item, **extra):
        body = {
            "source_sha256": item["source"]["sha256"],
            "proposal_sha256": item["proposal"]["proposal_sha256"],
            "confirmed": True,
            **extra,
        }
        return self.request(f"/api/reviews/{item['anomaly_id']}/authorize", body)

    def apply(self, item, authorization_id):
        return self.request(f"/api/reviews/{item['anomaly_id']}/apply", {
            "source_sha256": item["source"]["sha256"],
            "authorization_event_id": authorization_id,
            "confirmed": True,
        })

    def test_detection_is_read_only_and_exposes_all_three_known_categories(self):
        lifecycle, lifecycle_raw = self.invalid_source("events", "evt_bad_lifecycle.json", {
            **task_event("bad-lifecycle-001", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        step_position, step_position_raw = self.invalid_source(
            "step_events", "evt_bad_step_position.json",
            step_event("bad-step-position-001", "update", 0,
                       {"title": "候选标题", "position": 2}))
        completion, completion_raw = self.invalid_source(
            "step_events", "evt_bad_completion.json",
            step_event("bad-step-completion-001", "update", 1, {"status": "done"}))
        before = {path.name: path.read_bytes() for path in (lifecycle, step_position, completion)}
        result = self.reviews()
        self.assertEqual(result["summary"]["pending"], 3)
        self.assertEqual(result["summary"]["open_count"], 3)
        self.assertEqual({item["category"] for item in result["items"]}, {
            "task_lifecycle_requires_user", "step_update_position",
            "completion_confirmation_missing"})
        self.assertEqual({path.name: path.read_bytes() for path in (lifecycle, step_position, completion)}, before)
        self.assertFalse((self.data_dir / "review_events").exists())
        status, workspace = self.request("/api/tasks")
        self.assertEqual(status, 200)
        self.assertEqual(workspace["review_summary"]["open_count"], 3)
        self.assertEqual(len(workspace["warnings"]), 3)

    def test_lifecycle_repair_requires_authorization_then_writes_valid_event_and_receipt(self):
        source, original = self.invalid_source("events", "evt_lifecycle_needs_review.json", {
            **task_event("bad-lifecycle-002", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        self.assertIsNotNone(item["proposal"])
        self.assertEqual(item["proposal"]["event"]["actor"], "user")
        self.assertEqual(item["proposal"]["event"]["base_revision"], 1)
        self.assertEqual(self.request("/api/tasks")[1]["tasks"][0]["trashed_at"], None)
        code, result = self.authorize(item)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["status"], "authorized")
        self.assertEqual(self.request("/api/tasks")[1]["tasks"][0]["trashed_at"], None,
                         "authorization alone must not write a business event")
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)
        code, applied = self.apply(item, result["authorization_event_id"])
        self.assertEqual(code, 200, applied)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(source.read_bytes(), original, "the original invalid event is immutable")
        events = [json.loads(path.read_text("utf-8"))
                  for path in (self.data_dir / "events").glob("*.json")]
        repaired = next(event for event in events if event["event_id"] == applied["target_event_id"])
        self.assertEqual((repaired["action"], repaired["actor"], repaired["base_revision"]),
                         ("trash", "user", 1))
        self.assertEqual(self.request("/api/tasks")[1]["tasks"], [])
        self.assertEqual(len(self.request("/api/trash")[1]["tasks"]), 1)
        history = [json.loads(path.read_text("utf-8"))
                   for path in (self.data_dir / "review_events").glob("*.json")]
        self.assertEqual([entry["action"] for entry in sorted(history, key=lambda e: e["base_revision"])],
                         ["authorize", "applied"])
        refreshed = next(entry for entry in self.reviews()["items"]
                         if entry["anomaly_id"] == item["anomaly_id"])
        self.assertEqual(refreshed["status"], "applied")
        self.assertEqual(refreshed["timeline"][-1]["action"], "applied")
        code, repeated = self.apply(item, result["authorization_event_id"])
        self.assertEqual((code, repeated["status"], repeated["saved"]), (200, "applied", False))

    def test_step_position_repair_drops_illegal_position_and_keeps_history(self):
        source, original = self.invalid_source(
            "step_events", "evt_step_position_needs_review.json",
            step_event("bad-step-position-002", "update", 0,
                       {"title": "修复后的步骤标题", "position": 8}))
        item = self.item("step_update_position")
        self.assertEqual(item["proposal"]["event"]["changes"], {"title": "修复后的步骤标题"})
        code, auth = self.authorize(item)
        self.assertEqual(code, 200, auth)
        code, result = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200, result)
        task = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["steps"][0]["title"], "修复后的步骤标题")
        self.assertEqual(task["steps"][0]["revision"], 2)
        self.assertEqual(source.read_bytes(), original)
        repaired = next(json.loads(path.read_text("utf-8")) for path in
                        (self.data_dir / "step_events").glob("*.json")
                        if json.loads(path.read_text("utf-8"))["event_id"] == result["target_event_id"])
        self.assertNotIn("position", repaired["changes"])
        self.assertEqual(repaired["base_revision"], 1)

    def test_completion_repair_requires_a_second_explicit_confirmation(self):
        source, original = self.invalid_source(
            "step_events", "evt_step_completion_needs_review.json",
            step_event("bad-step-completion-002", "update", 1, {"status": "done"}))
        item = self.item("completion_confirmation_missing")
        self.assertTrue(item["proposal"]["requires_completion_confirmation"])
        code, result = self.authorize(item, confirm_completion=False)
        self.assertEqual(code, 400, result)
        self.assertFalse((self.data_dir / "review_events").exists())
        code, auth = self.authorize(item, confirm_completion=True)
        self.assertEqual(code, 200, auth)
        code, applied = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200, applied)
        task = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["steps"][0]["status"], "done")
        self.assertEqual(task["status"], "doing")
        self.assertTrue(task["step_completion_pending"])
        self.assertEqual(source.read_bytes(), original)
        repaired = next(json.loads(path.read_text("utf-8")) for path in
                        (self.data_dir / "step_events").glob("*.json")
                        if json.loads(path.read_text("utf-8"))["event_id"] == applied["target_event_id"])
        self.assertTrue(repaired["confirmed_done"])

    def test_invalid_step_id_is_explained_and_can_only_be_kept_without_writing(self):
        source, original = self.invalid_source(
            "step_events", "evt_bad_step_reference.json",
            {**step_event("bad-step-reference-001", "update", 1,
                          {"title": "需要核对的虚构步骤名称"}),
             "step_id": "STEP-not-a-valid-id"})
        item = self.item("invalid_step_reference")
        self.assertEqual(item["title"], "步骤操作未能确认目标")
        self.assertEqual(item["task_title"], "虚构治理测试任务")
        self.assertEqual(item["recorded_step_title"], "需要核对的虚构步骤名称")
        self.assertIsNone(item["proposal"])
        self.assertFalse(item["can_authorize"])
        self.assertTrue(item["can_dismiss"])
        self.assertIn("无法确认", item["user_guidance"]["summary"])
        self.assertIn("现有步骤没有因此改变", item["user_guidance"]["impact"])
        self.assertIn("正常编辑入口", item["user_guidance"]["recommendation"])
        self.assertIn("无法确认目标步骤", item["proposal_block_reason"])
        code, result = self.request(f"/api/reviews/{item['anomaly_id']}/dismiss", {
            "source_sha256": item["source"]["sha256"], "confirmed": True,
            "note": "已核对关联任务，无法确认该步骤编号对应的步骤，决定保留原记录。"})
        self.assertEqual(code, 200, result)
        self.assertEqual(source.read_bytes(), original)
        task = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual([step["title"] for step in task["steps"]], ["虚构步骤"])
        self.assertEqual(self.item("invalid_step_reference")["status"], "dismissed")

    def test_unsupported_invalid_json_can_only_be_dismissed_without_business_write(self):
        source = self.data_dir / "events" / "evt_malformed.json"
        source.write_bytes(b'{"version": 1, broken')
        original = source.read_bytes()
        item = self.item("malformed_event")
        self.assertIsNone(item["proposal"])
        code, result = self.request(f"/api/reviews/{item['anomaly_id']}/dismiss", {
            "source_sha256": item["source"]["sha256"], "confirmed": True,
            "note": "已核对来源，文件内容无法可靠恢复，暂不写入。"})
        self.assertEqual(code, 200, result)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)
        refreshed = next(entry for entry in self.reviews()["items"]
                         if entry["anomaly_id"] == item["anomaly_id"])
        self.assertEqual(refreshed["status"], "dismissed")

    def test_source_change_after_authorization_invalidates_it_without_writing(self):
        source, _ = self.invalid_source("events", "evt_lifecycle_tamper.json", {
            **task_event("bad-lifecycle-003", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        code, auth = self.authorize(item)
        self.assertEqual(code, 200)
        source.write_text(source.read_text("utf-8") + "\n", encoding="utf-8")
        code, result = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 409, result)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)
        self.assertEqual(app.read_workspace(self.data_dir, include_trashed=True)["tasks"][0]["trashed_at"], None)
        self.assertEqual(self.reviews()["summary"]["stale"], 1)

    def test_target_revision_change_after_authorization_invalidates_it(self):
        self.invalid_source("events", "evt_lifecycle_revision.json", {
            **task_event("bad-lifecycle-004", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        code, auth = self.authorize(item)
        self.assertEqual(code, 200)
        app.append_event(self.data_dir, task_event(
            "governance-independent-update-001", "update", 1, {"title": "合法并发修改"}))
        code, result = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 409, result)
        task = app.read_workspace(self.data_dir, include_trashed=True)["tasks"][0]
        self.assertEqual(task["title"], "合法并发修改")
        self.assertIsNone(task["trashed_at"])
        self.assertEqual(self.reviews()["summary"]["stale"], 1)

    def test_authorized_review_synced_to_another_device_does_not_auto_apply(self):
        self.invalid_source("events", "evt_lifecycle_remote.json", {
            **task_event("bad-lifecycle-005", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        code, auth = self.authorize(item)
        self.assertEqual(code, 200)
        with tempfile.TemporaryDirectory() as remote_temp:
            remote = Path(remote_temp) / "data"
            remote.mkdir()
            for folder in ("events", "step_events", "project_events", "review_events"):
                local_folder = self.data_dir / folder
                if local_folder.is_dir():
                    shutil.copytree(local_folder, remote / folder)
            remote_reviews = app.list_data_reviews(remote)
            remote_item = next(entry for entry in remote_reviews["items"]
                               if entry["anomaly_id"] == item["anomaly_id"])
            self.assertEqual(remote_item["status"], "authorized")
            self.assertTrue(remote_item["can_apply"])
            self.assertEqual(len(list((remote / "events").glob("*.json"))), 2,
                             "remote authorization alone must not create the repair event")
            self.assertEqual(len(list((remote / "review_events").glob("*.json"))), 1)

    def test_conflicting_review_authorizations_freeze_the_review_stream(self):
        self.invalid_source("events", "evt_lifecycle_review_conflict.json", {
            **task_event("bad-lifecycle-006", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        proposal = item["proposal"]
        event_a = app._new_review_record(item, "authorize", 0, {
            "approved_event": {**proposal["event"], "timestamp": app.utc_now()},
            "proposal_sha256": proposal["proposal_sha256"], "note": "设备甲核查"})
        event_b = app._new_review_record(item, "authorize", 0, {
            "approved_event": {**proposal["event"], "timestamp": app.utc_now()},
            "proposal_sha256": proposal["proposal_sha256"], "note": "设备乙核查"})
        app.append_review_event(self.data_dir, event_a)
        app.append_review_event(self.data_dir, event_b)
        refreshed = next(entry for entry in self.reviews()["items"]
                         if entry["anomaly_id"] == item["anomaly_id"])
        self.assertEqual(refreshed["status"], "conflict")
        self.assertFalse(refreshed["can_apply"])
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)

    def test_invalid_review_payloads_cannot_authorize_or_apply(self):
        self.invalid_source("events", "evt_lifecycle_invalid_payload.json", {
            **task_event("bad-lifecycle-007", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        base = f"/api/reviews/{item['anomaly_id']}"
        self.assertEqual(self.request(base + "/authorize", {
            "source_sha256": item["source"]["sha256"],
            "proposal_sha256": item["proposal"]["proposal_sha256"],
            "confirmed": False})[0], 400)
        self.assertEqual(self.request(base + "/apply", {
            "source_sha256": item["source"]["sha256"],
            "authorization_event_id": "fake-event-0001",
            "confirmed": True})[0], 409)
        self.assertEqual(self.request(base + "/dismiss", {
            "source_sha256": item["source"]["sha256"], "confirmed": True,
            "note": ""})[0], 400)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 2)
        self.assertFalse((self.data_dir / "review_events").exists())


    def test_invalid_restore_can_be_repaired_against_current_trashed_revision(self):
        app.append_event(self.data_dir, task_event(
            "governance-existing-trash-001", "trash", 1,
            {"trashed_at": "2026-11-03T04:05:00Z"}))
        source, original = self.invalid_source("events", "evt_bad_restore.json", {
            **task_event("bad-restore-001", "restore", 1, {"trashed_at": None}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        self.assertIsNotNone(item["proposal"])
        self.assertEqual(item["proposal"]["event"]["action"], "restore")
        self.assertEqual(item["proposal"]["event"]["base_revision"], 2)
        code, auth = self.authorize(item)
        self.assertEqual(code, 200, auth)
        code, result = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200, result)
        task = app.read_workspace(self.data_dir, include_trashed=True)["tasks"][0]
        self.assertIsNone(task["trashed_at"])
        self.assertEqual(task["revision"], 3)
        self.assertEqual(source.read_bytes(), original)

    def test_invalid_settings_event_is_discovered_and_can_only_be_reviewed(self):
        source = self.data_dir / "settings_events" / "evt_bad_retention.json"
        source.parent.mkdir(parents=True)
        source.write_bytes(b'{"version":1,"event_id":"broken-settings-001","key":"trash_retention_days","days":13}')
        original = source.read_bytes()
        item = self.item("invalid_event")
        self.assertEqual(item["source"]["folder"], "settings_events")
        self.assertIsNone(item["proposal"])
        code, result = self.request(f"/api/reviews/{item['anomaly_id']}/dismiss", {
            "source_sha256": item["source"]["sha256"], "confirmed": True,
            "note": "周期值不在允许范围内，保留原文件，暂不修改共享设置。"})
        self.assertEqual(code, 200, result)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(app.read_trash_retention(self.data_dir)[0], 30)
        self.assertEqual(len(list((self.data_dir / "events").glob("*.json"))), 1)


    def test_missing_applied_event_is_detected_and_requires_reauthorization(self):
        self.invalid_source("events", "evt_lifecycle_missing_receipt.json", {
            **task_event("bad-lifecycle-missing-001", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        code, auth = self.authorize(item)
        self.assertEqual(code, 200)
        code, applied = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200)
        target = self.data_dir / "events" / ("evt_" + applied["target_event_id"] + ".json")
        target.unlink()
        tracked = next(entry for entry in self.reviews()["items"]
                       if entry["anomaly_id"] == item["anomaly_id"])
        self.assertEqual(tracked["status"], "failed")
        self.assertTrue(tracked["can_authorize"])
        code, reauth = self.authorize(tracked, note="结果文件缺失，重新核对后授权恢复。")
        self.assertEqual(code, 200, reauth)
        code, recovered = self.apply(tracked, reauth["authorization_event_id"])
        self.assertEqual(code, 200, recovered)
        self.assertEqual(next(entry for entry in self.reviews()["items"]
                              if entry["anomaly_id"] == item["anomaly_id"])["status"], "applied")

    def test_changed_applied_event_receipt_is_a_conflict_and_never_overwritten(self):
        self.invalid_source("events", "evt_lifecycle_changed_receipt.json", {
            **task_event("bad-lifecycle-receipt-001", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        code, auth = self.authorize(item)
        self.assertEqual(code, 200)
        code, applied = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200)
        target = self.data_dir / "events" / ("evt_" + applied["target_event_id"] + ".json")
        target.write_bytes(target.read_bytes() + b" ")
        tampered = target.read_bytes()
        tracked = next(entry for entry in self.reviews()["items"]
                       if entry["anomaly_id"] == item["anomaly_id"])
        self.assertEqual(tracked["status"], "conflict")
        self.assertFalse(tracked["can_apply"])
        code, result = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 409, result)
        self.assertEqual(target.read_bytes(), tampered)


    def test_task_completion_repair_requires_explicit_user_confirmation(self):
        source, original = self.invalid_source("events", "evt_task_completion_needs_review.json", {
            **task_event("bad-task-completion-001", "update", 1, {"status": "done"})
        })
        item = self.item("completion_confirmation_missing")
        self.assertTrue(item["proposal"]["requires_completion_confirmation"])
        code, result = self.authorize(item, confirm_completion=False)
        self.assertEqual(code, 400, result)
        code, auth = self.authorize(item, confirm_completion=True)
        self.assertEqual(code, 200, auth)
        code, applied = self.apply(item, auth["authorization_event_id"])
        self.assertEqual(code, 200, applied)
        task = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["revision"], 2)
        self.assertEqual(source.read_bytes(), original)
        repaired = next(json.loads(path.read_text("utf-8")) for path in
                        (self.data_dir / "events").glob("*.json")
                        if json.loads(path.read_text("utf-8"))["event_id"] == applied["target_event_id"])
        self.assertTrue(repaired["confirmed_done"])

    def test_future_step_revision_waits_for_prior_anomaly_and_applies_in_order(self):
        app.append_step_event(self.data_dir, step_event(
            "governance-step-first-valid-update", "update", 1,
            {"title": "用户已确认的初始步骤标题"}))
        earlier_source, earlier_raw = self.invalid_source(
            "step_events", "evt_step_done_revision_2.json",
            step_event("bad-step-done-rev-2", "update", 2,
                       {"title": "较早版本的完成标题", "status": "done"},
                       actor="chatgpt", confirmed_done=True))
        later_source, later_raw = self.invalid_source(
            "step_events", "evt_step_done_revision_3.json",
            step_event("bad-step-done-rev-3", "update", 3,
                       {"title": "较新版本的完成标题", "status": "done"},
                       actor="chatgpt", confirmed_done=True))

        items = self.reviews()["items"]
        earlier = next(item for item in items if item["event_id"] == "bad-step-done-rev-2")
        later = next(item for item in items if item["event_id"] == "bad-step-done-rev-3")
        self.assertEqual(earlier["proposal"]["event"]["base_revision"], 2)
        self.assertIsNone(later["proposal"])
        self.assertIn("前序", later["proposal_block_reason"])
        self.assertFalse(later["can_authorize"])
        self.assertTrue(later["can_dismiss"])

        code, auth = self.authorize(earlier, confirm_completion=True)
        self.assertEqual(code, 200, auth)
        code, applied = self.apply(earlier, auth["authorization_event_id"])
        self.assertEqual(code, 200, applied)

        refreshed = self.reviews()["items"]
        later = next(item for item in refreshed if item["event_id"] == "bad-step-done-rev-3")
        self.assertIsNotNone(later["proposal"])
        self.assertEqual(later["proposal"]["event"]["base_revision"], 3)
        self.assertEqual(later["proposal"]["event"]["changes"], {"title": "较新版本的完成标题"})
        self.assertFalse(later["proposal"]["requires_completion_confirmation"],
                         "the earlier user-confirmed completion must remain valid")
        code, auth = self.authorize(later)
        self.assertEqual(code, 200, auth)
        code, applied = self.apply(later, auth["authorization_event_id"])
        self.assertEqual(code, 200, applied)

        task = app.read_workspace(self.data_dir)["tasks"][0]
        step = next(item for item in task["steps"] if item["step_id"] == STEP_ID)
        self.assertEqual(step["title"], "较新版本的完成标题")
        self.assertEqual(step["revision"], 4)
        self.assertEqual(earlier_source.read_bytes(), earlier_raw)
        self.assertEqual(later_source.read_bytes(), later_raw)

    def test_stale_task_trash_is_not_rebased_onto_a_newer_active_task(self):
        app.append_event(self.data_dir, task_event(
            "governance-task-newer-valid-update", "update", 1,
            {"title": "更新后的有效任务标题"}))
        source, original = self.invalid_source("events", "evt_stale_trash.json", {
            **task_event("bad-stale-trash-001", "trash", 1,
                         {"trashed_at": "2026-11-03T04:10:00Z"}, actor="chatgpt")
        })
        item = self.item("task_lifecycle_requires_user")
        self.assertIsNone(item["proposal"])
        self.assertIn("避免误将后续更新的任务移入回收站", item["proposal_block_reason"])
        self.assertFalse(item["can_authorize"])
        self.assertTrue(item["can_dismiss"])
        code, result = self.request(f"/api/reviews/{item['anomaly_id']}/dismiss", {
            "source_sha256": item["source"]["sha256"], "confirmed": True,
            "note": "该任务在原始 AI 回收站事件之后已有更新，保留当前任务，不执行过期回收站操作。"})
        self.assertEqual(code, 200, result)
        task = app.read_workspace(self.data_dir, include_trashed=True)["tasks"][0]
        self.assertIsNone(task["trashed_at"])
        self.assertEqual(task["title"], "更新后的有效任务标题")
        self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
