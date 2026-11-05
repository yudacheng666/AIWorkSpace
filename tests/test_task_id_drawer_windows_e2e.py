"""Isolated real Chromium regression for V2.0.1 task IDs and drawer behavior.

Only runs in the existing GitHub-hosted Windows Playwright job. All records
are fictional and live in a disposable temporary data directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import date, timedelta
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import append_event, append_step_event, handler_factory, read_workspace  # noqa: E402


@unittest.skipUnless(
    sys.platform == "win32"
    and os.environ.get("AIWORKSPACE_RUN_WINDOWS_E2E") == "1"
    and sync_playwright is not None,
    "isolated Windows Chromium job only",
)
class TaskIdDrawerChromiumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiworkspace-v201-ui-")
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "fictional-data"
        self.data_dir.mkdir()
        self.task_id = "TASK-" + "A" * 32
        self.short_id = "T-261102-" + "A" * 12
        append_event(self.data_dir, {
            "version": 1,
            "event_id": "v201-chromium-create-001",
            "task_id": self.task_id,
            "action": "create",
            "actor": "user",
            "timestamp": "2026-11-02T09:00:00Z",
            "base_revision": 0,
            "changes": {"title": "虚构任务：验证短编号及抽屉", "status": "todo"},
        })
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["display_id"], self.short_id)
        self.before = self._file_hashes()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.data_dir))
        self.port = self.server.server_port
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _file_hashes(self):
        return {
            item.relative_to(self.data_dir).as_posix():
                hashlib.sha256(item.read_bytes()).hexdigest()
            for item in self.data_dir.rglob("*") if item.is_file()
        }

    def _open_browser(self, open_detail=True):
        manager = sync_playwright().start()
        self.addCleanup(manager.stop)
        browser = manager.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        origin = f"http://127.0.0.1:{self.port}"
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        self.addCleanup(context.close)
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
        page = context.new_page()
        page.goto(origin + "/", wait_until="networkidle")
        page.locator("#nav-tasks").click()
        if open_detail:
            page.locator(".task-summary .task-summary-title").first.click()
            self.assertFalse(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        else:
            self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        return page


    def test_task_title_opens_detail_and_list_id_copies_without_opening(self):
        page = self._open_browser(open_detail=False)
        row = page.locator(".task-summary").first
        self.assertEqual(row.locator(".task-summary-title").inner_text(),
                         "虚构任务：验证短编号及抽屉")
        row.locator(".task-summary-id-copy").click()
        expect(row.locator(".task-summary-copy-feedback")).to_have_text("已复制")
        self.assertEqual(page.evaluate("navigator.clipboard.readText()"), self.short_id)
        self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"),
                        "copying the list ID must not open the drawer")
        row.locator(".task-summary-title").click()
        expect(page.locator("#task-detail-drawer")).to_be_visible()
        self.assertEqual(page.locator("#task-detail-title").inner_text(),
                         "虚构任务：验证短编号及抽屉")
        self.assertEqual(self._file_hashes(), self.before,
                         "opening and copying task list fields must not write task data")

    def test_task_list_quick_status_priority_and_confirmed_completion(self):
        """Real Chromium quick buttons use append-only events and exact revisions."""
        append_event(self.data_dir, {
            "version": 1, "event_id": "quick-other-task-create",
            "task_id": "TASK-" + "B" * 32, "action": "create",
            "actor": "user", "timestamp": "2026-11-02T09:00:00Z",
            "base_revision": 0,
            "changes": {"title": "虚构另一项未完成任务", "status": "todo"},
        })
        source = next(self.data_dir.glob("events/*.json"))
        source_bytes = source.read_bytes()
        page = self._open_browser(open_detail=False)
        row = page.locator(".task-summary").filter(has_text="虚构任务：验证短编号及抽屉")
        status = row.locator(".task-quick-editor--status .task-quick-trigger")
        priority = row.locator(".task-quick-editor--priority .task-quick-trigger")
        expect(status).to_have_text("待处理")
        expect(priority).to_have_text("普通")
        self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        self.assertEqual(len(list(self.data_dir.glob("events/*.json"))), 2)

        priority.click()
        row.get_by_role("button", name="设为紧急").click()
        expect(row.locator(".task-quick-editor--priority .task-quick-trigger")).to_have_text("紧急")
        task = next(x for x in read_workspace(self.data_dir)["tasks"] if x["task_id"] == self.task_id)
        self.assertEqual((task["priority"], task["revision"], task["status"]), ("urgent", 2, "todo"))
        self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))

        status = row.locator(".task-quick-editor--status .task-quick-trigger")
        status.click()
        row.get_by_role("button", name="设为进行中").click()
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_have_text("进行中")
        task = next(x for x in read_workspace(self.data_dir)["tasks"] if x["task_id"] == self.task_id)
        self.assertEqual((task["manual_status"], task["revision"]), ("doing", 3))

        status = row.locator(".task-quick-editor--status .task-quick-trigger")
        status.click()
        count_before = len(list(self.data_dir.glob("events/*.json")))
        page.once("dialog", lambda dialog: dialog.dismiss())
        row.get_by_role("button", name="设为已完成").click()
        self.assertEqual(len(list(self.data_dir.glob("events/*.json"))), count_before,
                         "declining completion must not append an event")
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_have_text("进行中")

        status.click()
        page.once("dialog", lambda dialog: dialog.accept())
        row.get_by_role("button", name="设为已完成").click()
        expect(page.locator("#tasks .task-summary-title").last).to_have_text(
            "虚构任务：验证短编号及抽屉")
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_have_text("已完成")
        task = next(x for x in read_workspace(self.data_dir)["tasks"] if x["task_id"] == self.task_id)
        self.assertEqual((task["status"], task["revision"]), ("done", 4))

        row.locator(".task-quick-editor--status .task-quick-trigger").click()
        row.get_by_role("button", name="设为待处理").click()
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_have_text("待处理")
        task = next(x for x in read_workspace(self.data_dir)["tasks"] if x["task_id"] == self.task_id)
        self.assertEqual((task["status"], task["revision"]), ("todo", 5))
        changes = [json.loads(p.read_text("utf-8")) for p in self.data_dir.glob("events/*.json")]
        updates = sorted((e for e in changes if e["task_id"] == self.task_id
                          and e["action"] == "update"), key=lambda e: e["base_revision"])
        self.assertEqual([e["changes"] for e in updates],
                         [{"priority": "urgent"}, {"status": "doing"},
                          {"status": "done"}, {"status": "todo"}])
        self.assertEqual([e["base_revision"] for e in updates], [1, 2, 3, 4])
        self.assertNotIn("confirmed_done", updates[0])
        self.assertNotIn("confirmed_done", updates[1])
        self.assertIs(updates[2].get("confirmed_done"), True)
        self.assertNotIn("confirmed_done", updates[3])
        self.assertEqual(source.read_bytes(), source_bytes, "original event is never overwritten")
        self.assertEqual(next(x for x in read_workspace(self.data_dir)["tasks"]
                              if x["task_id"] == "TASK-" + "B" * 32)["revision"], 1)

        page.set_viewport_size({"width": 390, "height": 800})
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_be_visible()
        expect(row.locator(".task-quick-editor--priority .task-quick-trigger")).to_be_visible()

    def test_parent_quick_status_restricts_override_and_reopens_to_child_rollup(self):
        """Real UI keeps child-driven state authoritative until explicit user confirmation."""
        child_id = "TASK-" + "C" * 32
        append_event(self.data_dir, {
            "version": 1, "event_id": "parent-quick-child-create",
            "task_id": child_id, "action": "create", "actor": "user",
            "timestamp": "2026-11-03T08:00:00Z", "base_revision": 0,
            "changes": {
                "title": "虚构子任务：供应商询价", "status": "todo",
                "parent_task_id": self.task_id
            },
        })
        append_event(self.data_dir, {
            "version": 1, "event_id": "parent-quick-child-doing",
            "task_id": child_id, "action": "update", "actor": "user",
            "timestamp": "2026-11-03T08:01:00Z", "base_revision": 1,
            "changes": {"status": "doing"},
        })
        originals = self._file_hashes()
        state = {t["task_id"]: t for t in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual(state[self.task_id]["status"], "doing")
        self.assertEqual(state[self.task_id]["manual_status"], "todo")
        self.assertEqual(state[self.task_id]["revision"], 1)

        page = self._open_browser(open_detail=False)
        parent = page.locator(".task-summary").filter(has_text="虚构任务：验证短编号及抽屉")
        status = parent.locator(".task-quick-editor--status .task-quick-trigger")
        expect(status).to_have_text("进行中")
        status.click()
        status_menu = parent.locator(".task-quick-editor--status .task-quick-menu")
        expect(status_menu).to_contain_text("当前状态由下级进度自动计算")
        expect(status_menu.locator("button")).to_have_count(1)
        expect(status_menu.get_by_role("button", name="确认完成任务")).to_be_visible()
        for blocked_label in ("设为待处理", "设为进行中", "设为受阻"):
            self.assertEqual(status_menu.get_by_role("button", name=blocked_label).count(), 0)
        page.keyboard.press("Escape")
        self.assertEqual(self._file_hashes(), originals, "opening menus must be read-only")

        # Parent priority is independent from the child-derived effective status.
        parent.locator(".task-quick-editor--priority .task-quick-trigger").click()
        parent.get_by_role("button", name="设为高").click()
        expect(parent.locator(".task-quick-editor--priority .task-quick-trigger")).to_have_text("高")
        state = {t["task_id"]: t for t in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual((state[self.task_id]["status"], state[self.task_id]["revision"]), ("doing", 2))

        status.click()
        count_before = len(list(self.data_dir.glob("events/*.json")))
        page.once("dialog", lambda dialog: dialog.dismiss())
        parent.get_by_role("button", name="确认完成任务").click()
        expect(status).to_have_text("进行中")
        self.assertEqual(len(list(self.data_dir.glob("events/*.json"))), count_before,
                         "declined confirmation must not write")

        status.click()
        page.once("dialog", lambda dialog: dialog.accept())
        parent.get_by_role("button", name="确认完成任务").click()
        expect(status).to_have_text("已完成")
        state = {t["task_id"]: t for t in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual((state[self.task_id]["status"], state[self.task_id]["manual_status"],
                          state[self.task_id]["revision"]), ("done", "done", 3))
        self.assertEqual(page.locator("#tasks .task-summary-title").last.inner_text(),
                         "虚构任务：验证短编号及抽屉")

        # A later child status change must not secretly reopen a confirmed parent.
        append_event(self.data_dir, {
            "version": 1, "event_id": "parent-quick-child-blocked",
            "task_id": child_id, "action": "update", "actor": "user",
            "timestamp": "2026-11-03T08:02:00Z", "base_revision": 2,
            "changes": {"status": "blocked"},
        })
        page.locator("#refresh").click()
        expect(status).to_have_text("已完成")
        status.click()
        menu = parent.locator(".task-quick-editor--status .task-quick-menu")
        expect(menu.locator("button")).to_have_count(1)
        expect(menu).to_contain_text("重新打开后")
        count_before = len(list(self.data_dir.glob("events/*.json")))
        page.once("dialog", lambda dialog: dialog.dismiss())
        parent.get_by_role("button", name="重新打开（恢复自动联动）").click()
        expect(status).to_have_text("已完成")
        self.assertEqual(len(list(self.data_dir.glob("events/*.json"))), count_before)

        status.click()
        page.once("dialog", lambda dialog: dialog.accept())
        parent.get_by_role("button", name="重新打开（恢复自动联动）").click()
        expect(status).to_have_text("受阻", timeout=10000)
        state = {t["task_id"]: t for t in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual((state[self.task_id]["status"], state[self.task_id]["manual_status"],
                          state[self.task_id]["revision"]), ("blocked", "todo", 4))
        self.assertEqual(state[child_id]["revision"], 3)
        self.assertEqual(state[self.task_id]["status_source"], "children")
        self.assertEqual(parent.locator(".task-quick-editor--priority .task-quick-trigger").inner_text(), "高")
        events = [json.loads(p.read_text("utf-8")) for p in self.data_dir.glob("events/*.json")]
        parent_updates = sorted((event for event in events if event["task_id"] == self.task_id
                                 and event["action"] == "update"), key=lambda event: event["base_revision"])
        self.assertEqual([event["changes"] for event in parent_updates],
                         [{"priority": "high"}, {"status": "done"}, {"status": "todo"}])
        self.assertEqual([event["base_revision"] for event in parent_updates], [1, 2, 3])
        self.assertIs(parent_updates[1].get("confirmed_done"), True)
        self.assertNotIn("confirmed_done", parent_updates[2])
        for relative_path, digest in originals.items():
            current_file = self.data_dir / relative_path
            self.assertEqual(hashlib.sha256(current_file.read_bytes()).hexdigest(), digest,
                             "original event files must never be overwritten")

    def test_task_list_quick_buttons_reject_stale_revision_and_conflict(self):
        page = self._open_browser(open_detail=False)
        row = page.locator(".task-summary").first
        append_event(self.data_dir, {
            "version": 1, "event_id": "quick-external-status-update",
            "task_id": self.task_id, "action": "update", "actor": "user",
            "timestamp": "2026-11-02T09:05:00Z", "base_revision": 1,
            "changes": {"status": "doing"},
        })
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["revision"], 2)
        row.locator(".task-quick-editor--priority .task-quick-trigger").click()
        row.get_by_role("button", name="设为高").click()
        expect(row.locator(".task-quick-editor--priority .task-quick-feedback")).to_contain_text(
            "任务已在别处更新或存在冲突")
        expect(row.locator(".task-quick-editor--priority .task-quick-trigger")).to_have_text("普通")
        self.assertEqual(len(list(self.data_dir.glob("events/*.json"))), 2,
                         "stale quick save must not write an event")
        page.locator("#refresh").click()
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_have_text("进行中")
        row.locator(".task-quick-editor--priority .task-quick-trigger").click()
        row.get_by_role("button", name="设为高").click()
        expect(row.locator(".task-quick-editor--priority .task-quick-trigger")).to_have_text("高")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["revision"], 3)

        append_event(self.data_dir, {
            "version": 1, "event_id": "quick-conflict-a",
            "task_id": self.task_id, "action": "update", "actor": "user",
            "timestamp": "2026-11-02T09:06:00Z", "base_revision": 3,
            "changes": {"status": "blocked"},
        })
        append_event(self.data_dir, {
            "version": 1, "event_id": "quick-conflict-b",
            "task_id": self.task_id, "action": "update", "actor": "user",
            "timestamp": "2026-11-02T09:06:01Z", "base_revision": 3,
            "changes": {"status": "todo"},
        })
        page.locator("#refresh").click()
        expect(row.locator(".task-quick-editor--status .task-quick-trigger")).to_be_disabled()
        expect(row.locator(".task-quick-editor--priority .task-quick-trigger")).to_be_disabled()

    def test_completed_tasks_remain_at_end_for_default_and_column_sorts(self):
        for suffix, title, status, due, priority in [
            ("B", "虚构待处理任务", "todo", "2026-11-08", "low"),
            ("C", "虚构进行中任务", "doing", "2026-11-03", "urgent"),
            ("D", "虚构已完成任务", "done", "2026-11-01", "high"),
        ]:
            task_id = "TASK-" + suffix * 32
            append_event(self.data_dir, {
                "version": 1, "event_id": "task-list-sort-create-" + suffix,
                "task_id": task_id, "action": "create", "actor": "user",
                "timestamp": "2026-11-02T09:00:00Z", "base_revision": 0,
                "changes": {"title": title, "status": "todo",
                            "due_date": due, "priority": priority}
            })
            if status == "doing":
                append_event(self.data_dir, {
                    "version": 1, "event_id": "task-list-sort-doing-" + suffix,
                    "task_id": task_id, "action": "update", "actor": "user",
                    "timestamp": "2026-11-02T09:01:00Z", "base_revision": 1,
                    "changes": {"status": "doing"}
                })
            elif status == "done":
                append_event(self.data_dir, {
                    "version": 1, "event_id": "task-list-sort-done-" + suffix,
                    "task_id": task_id, "action": "update", "actor": "user",
                    "timestamp": "2026-11-02T09:01:00Z", "base_revision": 1,
                    "changes": {"status": "done"}, "confirmed_done": True
                })
        self.before = self._file_hashes()
        page = self._open_browser(open_detail=False)
        titles = page.locator("#tasks .task-summary-title")
        self.assertEqual(titles.last.inner_text(), "虚构已完成任务")
        for mode in ("due", "priority", "title"):
            page.locator("#task-sort").select_option(mode)
            self.assertEqual(page.locator("#tasks .task-summary-title").last.inner_text(),
                             "虚构已完成任务", mode + " sort must keep completed tasks last")
        page.locator("#task-sort").select_option("project")
        page.locator("#task-list-columns details[data-field='due'] summary").click()
        page.locator("#task-list-columns details[data-field='due']").get_by_role(
            "button", name="升序").click()
        page.locator("#task-list-columns details[data-field='priority'] summary").click()
        page.locator("#task-list-columns details[data-field='priority']").get_by_role(
            "button", name="降序").click()
        self.assertEqual(page.locator("#tasks .task-summary-title").last.inner_text(),
                         "虚构已完成任务", "multi-column sorting must keep completed tasks last")
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 4)
        self.assertEqual(self._file_hashes(), self.before,
                         "task ordering must remain a read-only presentation change")

    def test_last_refresh_status_is_in_sidebar_footer_and_does_not_shift_task_toolbar(self):
        page = self._open_browser()
        status = page.locator(".sidebar-footnote #sync")
        expect(status).to_be_visible()
        expect(status).to_contain_text("上次刷新")
        self.assertEqual(page.locator(".section-actions #sync").count(), 0)
        before = page.locator(".section-actions").bounding_box()
        self.assertIsNotNone(before)
        page.evaluate("refresh(true)")
        expect(status).to_contain_text("上次刷新")
        after = page.locator(".section-actions").bounding_box()
        self.assertIsNotNone(after)
        self.assertEqual(before["width"], after["width"])
        self.assertEqual(before["height"], after["height"])
        self.assertEqual(self._file_hashes(), self.before,
                         "refresh status updates must not write task data")

    def test_short_id_copy_and_backdrop(self):
        page = self._open_browser()
        self.assertEqual(page.locator(".task-summary-id").first.inner_text(), self.short_id)
        self.assertEqual(page.locator("#task-detail-id").inner_text(), self.short_id)

        page.locator("#task-id-copy").click()
        # Locator waiting works under the app's strict CSP, unlike
        # page.wait_for_function(), which uses unsafe-eval.
        page.locator("#task-id-feedback").wait_for(state="visible")
        self.assertEqual(page.locator("#task-id-feedback").inner_text(), "已复制")
        self.assertEqual(page.evaluate("navigator.clipboard.readText()"), self.short_id)
        page.locator("#task-detail-id").click()
        self.assertEqual(page.evaluate("navigator.clipboard.readText()"), self.short_id)

        # Clicking inside the drawer must not close it.
        page.locator("#task-detail-content").click(position={"x": 5, "y": 5})
        self.assertFalse(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        # Clicking the dimmed page, outside the right-side panel, closes cleanly.
        page.mouse.click(140, 400)
        self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        self.assertEqual(self._file_hashes(), self.before)


    def test_v202_document_link_and_safe_trash_restore_purge(self):
        """Real UI exercises all three storage transitions on fictional data."""
        page = self._open_browser()
        page.locator(".step-add-form input").fill("虚构文档关联步骤")
        page.locator(".step-add-form button").click()
        page.locator(".step-row").wait_for(state="visible")
        doc_panel = page.locator("#task-detail-content .step-row .doc-panel")
        expect(doc_panel.locator(".doc-panel-toggle")).to_have_text("添加文档")
        expect(doc_panel.locator(".doc-panel-content")).to_be_hidden()
        doc_panel.locator(".doc-panel-toggle").click()
        document = doc_panel.locator(".doc-add-form")
        document.locator("input[type='text']").fill("虚构云端计划")
        document.locator("input[type='url']").fill(
            "https://drive.google.com/file/d/SYNTHETIC_DOC_TEST/view")
        title_editor = page.locator("#task-detail-content .task-form input[type='text']").first
        original_title = title_editor.input_value()
        title_editor.fill("虚构未保存的任务草稿")
        document.get_by_role("button", name="添加链接").click()
        page.get_by_text("其他任务或步骤有未保存的草稿", exact=False).wait_for(state="visible")
        self.assertEqual(title_editor.input_value(), "虚构未保存的任务草稿")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["title"], original_title)
        # Once the other draft is restored to its original baseline, adding
        # the link must succeed without losing or overwriting the task.
        title_editor.fill(original_title)
        document.get_by_role("button", name="添加链接").click()
        # First wait for the asynchronous save+refresh to render the *new*
        # document count; otherwise opening the old panel can be undone
        # by the subsequent refresh and look like a missing link.
        toggle = page.locator("#task-detail-content .step-row .doc-panel-toggle")
        expect(toggle).to_have_text("关联文档（1）")
        doc_body = page.locator("#task-detail-content .step-row .doc-panel-content")
        if not doc_body.is_visible():
            toggle.click()
        link = page.locator("#task-detail-content .doc-row a").first
        expect(link).to_be_visible()
        self.assertEqual(link.inner_text(), "虚构云端计划")
        self.assertEqual(
            link.get_attribute("href"),
            "https://drive.google.com/file/d/SYNTHETIC_DOC_TEST/view")
        self.assertEqual(link.get_attribute("target"), "_blank")
        self.assertEqual(link.get_attribute("rel"), "noopener noreferrer")
        task = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(task["document_links"], [])
        self.assertEqual(len(task["steps"][0]["document_links"]), 1)

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".task-lifecycle-controls button").click()
        page.locator("#task-detail-drawer").wait_for(state="hidden")
        self.assertEqual(read_workspace(self.data_dir)["tasks"], [])

        page.locator("#nav-trash").click()
        self.assertFalse(page.locator("#page-trash").evaluate("(e) => e.hidden"))
        self.assertIn("is-active", page.locator("#nav-trash").get_attribute("class"))
        row = page.locator(".trash-row").first
        row.wait_for(state="visible")
        self.assertIn("虚构任务", row.inner_text())
        self.assertTrue(page.locator(".trash-settings-card").is_visible())
        self.assertTrue(page.locator(".trash-list-card").is_visible())
        self.assertEqual(page.locator("#trash-stat-total").inner_text(), "1")
        self.assertEqual(page.locator("#trash-stat-restorable").inner_text(), "1")
        self.assertEqual(page.locator("#trash-stat-conflict").inner_text(), "0")
        self.assertEqual(page.locator("#trash-count").inner_text(), "1 项")
        self.assertEqual(page.locator("#trash-selection-count").inner_text(), "已选 0 项")
        self.assertTrue(page.locator("#trash-purge-selected").is_disabled())
        self.assertIn("trash-action--restore",
                        row.get_by_role("button", name="恢复").get_attribute("class"))
        page.locator("#trash-select-all").click()
        self.assertEqual(page.locator("#trash-selection-count").inner_text(), "已选 1 项")
        self.assertFalse(page.locator("#trash-purge-selected").is_disabled())
        self.assertEqual(page.locator("#trash-select-all").inner_text(), "取消全选")
        page.locator("#trash-select-all").click()
        self.assertEqual(page.locator("#trash-selection-count").inner_text(), "已选 0 项")
        self.assertTrue(page.locator("#trash-purge-selected").is_disabled())
        page.once("dialog", lambda dialog: dialog.accept())
        row.get_by_role("button", name="恢复").click()
        page.locator(".trash-row").wait_for(state="hidden")
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 1)
        page.locator("#nav-tasks").click()
        self.assertTrue(page.locator("#page-trash").evaluate("(e) => e.hidden"))

        page.locator(".task-summary .task-open").first.click()
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".task-lifecycle-controls button").click()
        page.locator("#task-detail-drawer").wait_for(state="hidden")
        page.locator("#nav-trash").click()
        row = page.locator(".trash-row").first
        row.wait_for(state="visible")
        row.locator("input[type='checkbox']").check()
        self.assertEqual(page.locator("#trash-selection-count").inner_text(), "已选 1 项")
        self.assertFalse(page.locator("#trash-purge-selected").is_disabled())
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#trash-purge-selected").click()
        page.locator(".trash-row").wait_for(state="hidden")
        self.assertEqual(read_workspace(self.data_dir, include_trashed=True)["tasks"], [])
        remaining = list((self.data_dir / "events").glob("*.json"))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(json.loads(remaining[0].read_text("utf-8"))["action"], "purge")

    def test_step_delete_hides_step_and_links_without_deleting_cloud_document(self):
        page = self._open_browser()
        page.locator(".step-add-form input").fill("步骤一 · 测试删除")
        page.locator(".step-add-form button").click()
        expect(page.locator(".step-row")).to_have_count(1)
        step = read_workspace(self.data_dir)["tasks"][0]["steps"][0]
        self.assertEqual(step["title"], "步骤一 · 测试删除")
        doc_panel = page.locator(".step-row .doc-panel")
        expect(doc_panel.locator(".doc-panel-content")).to_be_hidden()
        doc_panel.locator(".doc-panel-toggle").click()
        doc_panel.locator(".doc-add-form input[type='text']").fill("虚构关联资料")
        doc_panel.locator(".doc-add-form input[type='url']").fill(
            "https://drive.google.com/file/d/SYNTHETIC_STEP_FILE/view")
        doc_panel.locator(".doc-add-form button.save").click()
        page.locator(".step-row .doc-panel-toggle").click()
        expect(page.locator(".step-row .doc-row")).to_have_count(1)
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator(".step-row .step-delete").click()
        expect(page.locator(".step-row")).to_have_count(1)
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"][0]["steps"]), 1)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".step-row .step-delete").click()
        expect(page.locator(".step-row")).to_have_count(0)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["steps"], [])
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "todo")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["revision"], 1)
        events = [json.loads(p.read_text("utf-8"))
                  for p in (self.data_dir / "step_events").glob("*.json")]
        self.assertEqual(len([e for e in events if e["action"] == "delete"]), 1)
        self.assertTrue(any(e.get("changes", {}).get("document_links") for e in events))
        self.assertFalse((self.data_dir / "documents").exists(),
                         "step link removal must not alter Google Drive files")

    def test_v202_step_status_updates_task_without_automatic_done(self):
        page = self._open_browser()
        page.locator(".step-add-form input").fill("虚构第一步")
        page.locator(".step-add-form button").click()
        page.locator(".step-row").wait_for(state="visible")
        page.locator(".step-edit-form select").first.select_option("doing")
        page.locator(".step-edit-form button.save").first.click()
        expect(page.locator("#task-detail-content .task-form select").first).to_have_value("doing", timeout=10000)
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "doing")

        page.locator(".step-edit-form select").first.select_option("blocked")
        page.locator(".step-edit-form button.save").first.click()
        expect(page.locator("#task-detail-content .task-form select").first).to_have_value("blocked", timeout=10000)
        page.locator("#task-detail-content .step-status-note").wait_for(state="visible")
        self.assertEqual(read_workspace(self.data_dir)["tasks"][0]["status"], "blocked")
        self.assertEqual(page.locator(".task-form select").first.input_value(), "blocked")

        page.locator(".step-edit-form select").first.select_option("done")
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".step-edit-form button.save").first.click()
        page.get_by_text("全部执行步骤已完成", exact=False).wait_for(state="visible")
        state = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(state["status"], "doing")
        self.assertTrue(state["step_completion_pending"])
        self.assertEqual(state["manual_status"], "todo")

        page.locator(".task-form select").first.select_option("done")
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".task-form button.save").first.click()
        # A "hidden" locator may be true before the asynchronous POST even
        # starts. Wait for the save-success event written after refresh instead.
        expect(page.locator("#sync")).to_contain_text("保存成功", timeout=10000)
        state = read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(state["manual_status"], "done")
        self.assertEqual(state["status"], "done")


    def test_column_headings_multi_filter_sort_preserve_original_cards(self):
        # Additional fictional tasks allow verifying global filters and sort.
        for suffix, title, owner, due, priority in [
            ("B", "虚构采购任务", "虚构甲", "2026-11-07", "high"),
            ("C", "虚构生产任务", "虚构乙", "2026-11-04", "urgent")]:
            append_event(self.data_dir, {
                "version": 1, "event_id": "column-create-" + suffix,
                "task_id": "TASK-" + suffix * 32, "action": "create",
                "actor": "user", "timestamp": "2026-11-02T09:00:00Z",
                "base_revision": 0,
                "changes": {"title": title, "status": "todo", "owner": owner,
                            "due_date": due, "priority": priority}
            })
        page = self._open_browser()
        page.locator("#task-detail-close").click()
        expect(page.locator("#task-list-columns .task-column-head")).to_have_count(6)
        self.assertEqual(page.locator("#tasks .task-summary").count(), 3)
        page.locator("#task-list-columns details[data-field='owner'] summary").click()
        owner_menu = page.locator("#task-list-columns details[data-field='owner']")
        for checkbox in owner_menu.locator(".task-column-choice input").all():
            checkbox.uncheck()
        owner_menu.locator(".task-column-choice").filter(has_text="虚构甲").locator("input").check()
        owner_menu.get_by_role("button", name="应用筛选").click()
        expect(page.locator("#tasks .task-summary")).to_have_count(1)
        expect(page.locator("#tasks .task-summary-title")).to_have_text("虚构采购任务")
        page.locator("#task-columns-clear").click()
        expect(page.locator("#tasks .task-summary")).to_have_count(3)
        page.locator("#task-list-columns details[data-field='due'] summary").click()
        page.locator("#task-list-columns details[data-field='due']").get_by_role(
            "button", name="升序").click()
        page.locator("#task-list-columns details[data-field='priority'] summary").click()
        page.locator("#task-list-columns details[data-field='priority']").get_by_role(
            "button", name="降序").click()
        expect(page.locator("#tasks .task-summary")).to_have_count(3)
        self.assertTrue(all("task-summary" in name for name in
                            page.locator("#tasks > article").evaluate_all(
                                "(nodes) => nodes.map(n => n.className)")))
        self.assertEqual(page.locator("#task-list-columns details[data-field='due'] .task-column-indicator").inner_text().strip(),
                         "↑1 ▾")
        self.assertEqual(page.locator("#task-list-columns details[data-field='priority'] .task-column-indicator").inner_text().strip(),
                         "↓2 ▾")
        self.assertEqual(len(read_workspace(self.data_dir)["tasks"]), 3)

    def test_explicit_child_status_updates_parent_and_title_save_does_not_leak_manual(self):
        page = self._open_browser()
        page.locator("#task-detail-close").click()
        page.locator("#open-create-task").click()
        page.locator("#new-task-title").fill("虚构二级任务")
        page.locator("#new-task-parent").select_option(self.task_id)
        page.locator("#create-submit").click()
        expect(page.locator(".task-summary")).to_have_count(2, timeout=10000)

        child_row = page.locator(".task-summary").filter(has_text="虚构二级任务").first
        child_row.locator(".task-open").click()
        parent_choice = page.locator("#task-detail-content .task-form select").nth(1)
        self.assertEqual(parent_choice.input_value(), self.task_id)
        page.locator("#task-detail-content .task-form select").first.select_option("doing")
        page.locator("#task-detail-content .task-form button.save").first.click()
        expect(page.locator("#sync")).to_contain_text("保存成功", timeout=10000)
        tasks = {task["task_id"]: task for task in read_workspace(self.data_dir)["tasks"]}
        self.assertEqual(tasks[self.task_id]["status"], "doing")
        self.assertEqual(tasks[self.task_id]["manual_status"], "todo")
        self.assertEqual(tasks[self.task_id]["status_source"], "children")
        self.assertEqual(tasks[self.task_id]["revision"], 1)

        page.locator("#task-detail-close").click()
        parent_row = page.locator(".task-summary").filter(has_text="虚构任务：验证短编号及抽屉")
        expect(parent_row.locator(".status-pill")).to_have_text("进行中")
        parent_row.locator(".task-open").click()
        expect(page.locator("#task-detail-content .step-status-note")).to_contain_text("由子任务自动联动")
        title = page.locator("#task-detail-content .task-form input[type='text']").first
        title.fill("只修改上层任务名称")
        page.locator("#task-detail-content .task-form button.save").first.click()
        expect(page.locator(".task-summary").filter(has_text="只修改上层任务名称")).to_have_count(
            1, timeout=10000)
        parent = next(t for t in read_workspace(self.data_dir)["tasks"] if t["task_id"] == self.task_id)
        self.assertEqual(parent["status"], "doing")
        self.assertEqual(parent["manual_status"], "todo",
                         "title-only save must not convert derived doing into manual status")
        self.assertEqual(parent["revision"], 2)

    def test_unsaved_draft_cannot_be_silently_discarded(self):
        page = self._open_browser()
        title = page.locator("#task-detail-content .task-form input[type='text']").first
        title.fill("虚构未保存修改，请保留")
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.mouse.click(140, 400)
        self.assertFalse(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        self.assertEqual(title.input_value(), "虚构未保存修改，请保留")
        self.assertEqual(self._file_hashes(), self.before)

        page.once("dialog", lambda dialog: dialog.accept())
        page.mouse.click(140, 400)
        self.assertTrue(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        self.assertEqual(self._file_hashes(), self.before)




    def test_step_dates_calendar_gantt_and_bidirectional_conversion_in_real_chromium(self):
        today = date.today()
        initial_planned = (today + timedelta(days=1)).isoformat()
        initial_follow_up = (today + timedelta(days=2)).isoformat()
        initial_due = (today + timedelta(days=3)).isoformat()
        planned = (today + timedelta(days=2)).isoformat()
        follow_up = (today + timedelta(days=3)).isoformat()
        due = (today + timedelta(days=4)).isoformat()
        step_id = "STEP-" + "C" * 32
        append_step_event(self.data_dir, {
            "version": 1, "event_id": "step-dates-conversion-create",
            "task_id": self.task_id, "step_id": step_id, "action": "create",
            "actor": "user", "timestamp": "2026-11-05T09:00:00Z",
            "base_revision": 0,
            "changes": {"title": "虚构采购步骤：整理报价", "position": 1,
                        "planned_date": initial_planned, "due_date": initial_due,
                        "follow_up_date": initial_follow_up},
        })
        page = self._open_browser(open_detail=True)
        step_row = page.locator("#step-" + step_id)
        dates = step_row.locator(".step-date-fields input[type=date]")
        expect(dates).to_have_count(3)
        dates.nth(0).fill(planned)
        dates.nth(1).fill(due)
        dates.nth(2).fill(follow_up)
        step_row.get_by_role("button", name="保存步骤").click()
        # The input retains the typed value before the asynchronous save completes.
        # Poll the real append-only reducer, not the live input, to prove persistence.
        deadline = time.monotonic() + 10
        step = None
        while time.monotonic() < deadline:
            step = next((item for item in read_workspace(self.data_dir)["tasks"][0]["steps"]
                         if item["step_id"] == step_id), None)
            if step and (step["planned_date"], step["due_date"], step["follow_up_date"]) == (
                    planned, due, follow_up):
                break
            time.sleep(0.1)
        self.assertIsNotNone(step)
        self.assertEqual((step["planned_date"], step["due_date"], step["follow_up_date"]),
                         (planned, due, follow_up))
        stream_hashes = {
            path.relative_to(self.data_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ("events", "step_events") for path in (self.data_dir / folder).glob("*.json")
        }

        page.locator("#task-detail-close").click()
        expect(page.locator("#task-detail-drawer")).to_be_hidden()
        page.locator("#nav-calendar").click()
        expect(page.locator(".calendar-grid")).to_be_visible()
        expect(page.locator(".calendar-grid .calendar-step").filter(
            has_text="虚构采购步骤：整理报价")).to_have_count(1)
        page.locator("#nav-gantt").click()
        expect(page.locator(".gantt-step-row").filter(
            has_text="虚构采购步骤：整理报价")).to_have_count(1)

        page.locator("#nav-tasks").click()
        page.locator(".task-summary").filter(
            has_text="虚构任务：验证短编号及抽屉").locator(".task-summary-title").click()
        expect(page.locator("#step-" + step_id)).to_be_visible()
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#step-" + step_id).get_by_role("button", name="转为任务").click()
        expect(page.locator("#step-" + step_id)).to_have_count(0)
        parent_state = {item["task_id"]: item for item in read_workspace(self.data_dir)["tasks"]}
        parent = parent_state[self.task_id]
        self.assertEqual(parent["steps"], [])
        child = next(item for item in parent_state.values() if item.get("parent_task_id") == self.task_id)
        self.assertEqual((child["title"], child["planned_date"], child["due_date"],
                          child["follow_up_date"]), (
            "虚构采购步骤：整理报价", planned, due, follow_up))
        self.assertEqual(len(list((self.data_dir / "conversion_events").glob("*.json"))), 1)

        child_button = page.locator("#task-detail-content .child-tasks-panel").get_by_role(
            "button", name=re.compile("虚构采购步骤：整理报价"))
        child_button.click()
        expect(page.locator("#task-detail-title")).to_have_text("虚构采购步骤：整理报价")
        selector = page.locator(".task-conversion-panel select")
        selector.select_option(self.task_id)
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="转为该任务的步骤").click()
        expect(page.locator("#task-detail-drawer")).to_be_hidden()

        final = {item["task_id"]: item for item in read_workspace(self.data_dir)["tasks"]}
        parent = final[self.task_id]
        self.assertEqual(len(parent["steps"]), 1)
        moved_step = parent["steps"][0]
        self.assertNotEqual(moved_step["step_id"], step_id)
        self.assertEqual((moved_step["title"], moved_step["planned_date"],
                          moved_step["due_date"], moved_step["follow_up_date"]),
                         ("虚构采购步骤：整理报价", planned, due, follow_up))
        self.assertFalse(any(item.get("parent_task_id") == self.task_id for item in final.values()))
        self.assertEqual(len(list((self.data_dir / "conversion_events").glob("*.json"))), 2)
        after_streams = {
            path.relative_to(self.data_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ("events", "step_events") for path in (self.data_dir / folder).glob("*.json")
        }
        self.assertEqual(after_streams, stream_hashes,
                         "conversion transactions must not rewrite either original event stream")

        page.locator("#nav-calendar").click()
        expect(page.locator(".calendar-grid .calendar-step").filter(
            has_text="虚构采购步骤：整理报价")).to_have_count(1)
        page.locator("#nav-gantt").click()
        expect(page.locator(".gantt-step-row").filter(
            has_text="虚构采购步骤：整理报价")).to_have_count(1)

    def test_recurring_task_ui_completion_end_and_resume(self):
        """Real Chromium demonstrates the recurring task user workflow and append-only writes."""
        initial = self._file_hashes()
        page = self._open_browser()
        panel = page.locator(".recurrence-panel")
        expect(panel).to_contain_text("周期性任务")
        panel.locator("select").select_option("daily")
        panel.locator('input[type="number"]').fill("1")
        panel.locator('input[type="date"]').fill(date.today().isoformat())
        page.once("dialog", lambda dialog: dialog.accept())
        panel.get_by_role("button", name="启用周期任务").click()
        expect(page.locator(".recurrence-panel")).to_contain_text("本周期：")
        task = next(t for t in read_workspace(self.data_dir)["tasks"] if t["task_id"] == self.task_id)
        self.assertTrue(task["recurrence_active"])
        self.assertEqual(task["status"], "todo")
        self.assertEqual(page.evaluate(
            "(id) => taskEffectiveDate(current.find(t => t.task_id === id), 'planned_date')",
            self.task_id), task["recurrence_period_start"])
        self.assertEqual(page.evaluate(
            "(id) => taskEffectiveDate(current.find(t => t.task_id === id), 'due_date')",
            self.task_id), task["recurrence_period_end"])

        form = page.locator("#task-detail-content .task-form")
        form.locator("select").first.select_option("done")
        page.once("dialog", lambda dialog: dialog.accept())
        form.get_by_role("button", name="保存修改").click()
        expect(page.locator(".recurrence-panel")).to_contain_text("本周期已完成")
        task = next(t for t in read_workspace(self.data_dir)["tasks"] if t["task_id"] == self.task_id)
        self.assertEqual(task["status"], "done")

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".recurrence-panel").get_by_role(
            "button", name="彻底结束循环").click()
        expect(page.locator(".recurrence-panel")).to_contain_text("已彻底结束循环")
        task = next(t for t in read_workspace(self.data_dir)["tasks"] if t["task_id"] == self.task_id)
        self.assertTrue(task["recurrence_ended"])
        self.assertEqual(task["status"], "done")

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".recurrence-panel").get_by_role("button", name="恢复循环").click()
        expect(page.locator(".recurrence-panel")).to_contain_text("本周期未完成")
        task = next(t for t in read_workspace(self.data_dir)["tasks"] if t["task_id"] == self.task_id)
        self.assertTrue(task["recurrence_active"])
        self.assertEqual(task["status"], "todo")
        for relative, digest in initial.items():
            self.assertEqual(self._file_hashes().get(relative), digest,
                             "existing event files must stay byte-for-byte unchanged")
        actions = [json.loads(p.read_text("utf-8"))
                   for p in self.data_dir.glob("events/*.json")]
        self.assertEqual(len(actions), 5)
        self.assertTrue(any(event["changes"].get("status") == "done" and
                            event.get("confirmed_done") for event in actions))
        self.assertTrue(any(event.get("confirmed_end") for event in actions))

    def test_notification_inbox_is_read_only_and_displays_stable_message_id(self):
        source = self.data_dir / "events" / "evt_invalid_lifecycle_notification.json"
        invalid = {
            "version": 1,
            "event_id": "bad-lifecycle-notification-001",
            "task_id": self.task_id,
            "action": "trash",
            "actor": "chatgpt",
            "timestamp": "2026-11-03T04:10:00Z",
            "base_revision": 1,
            "changes": {"trashed_at": "2026-11-03T04:10:00Z"},
        }
        source.write_text(json.dumps(invalid, ensure_ascii=False, indent=2), encoding="utf-8")
        original = source.read_bytes()
        page = self._open_browser()
        # _open_browser opens the task drawer; close it through the real backdrop first.
        page.mouse.click(140, 400)
        page.locator("#nav-reviews").click()
        expect(page.locator("#page-reviews h1")).to_have_text("通知信箱")
        expect(page.locator("#review-list .inbox-message")).to_have_count(1)
        message = page.locator("#review-list .inbox-message")
        expect(message.locator(".inbox-type")).to_have_text("任务记录异常")
        expect(message.locator(".inbox-status")).to_have_text("待关注")
        message_id = message.locator(".inbox-message-id").inner_text()
        self.assertRegex(message_id, r"MSG-\d{6}-[A-F0-9]{12,32}")
        expect(page.locator("#review-list button")).to_have_count(0)
        details = message.locator(".inbox-message-details")
        self.assertFalse(details.evaluate("(element) => element.open"),
                         "message details must be collapsed by default")
        details.locator("summary").click()
        expect(details.locator(".inbox-message-detail-content")).to_contain_text("影响：")
        expect(details.locator(".inbox-message-detail-content")).to_contain_text("建议：")
        visible_text = message.inner_text()
        self.assertNotIn("ANOM-", visible_text)
        self.assertNotIn("SHA-256", visible_text)
        self.assertNotIn("bad-lifecycle-notification-001", visible_text)
        self.assertNotIn("chatgpt", visible_text)
        self.assertNotIn("evt_invalid_lifecycle_notification.json", visible_text)

        page.locator("#review-refresh").click()
        expect(page.locator("#review-list .inbox-message")).to_have_count(1)
        expect(page.locator(".inbox-message-id")).to_have_text(message_id)
        self.assertEqual(page.locator(".inbox-message-id").inner_text(), message_id,
                         "message ID must remain stable after a read-only refresh")
        self.assertEqual(source.read_bytes(), original,
                         "opening and refreshing the inbox must not change the invalid source event")
        self.assertFalse((self.data_dir / "review_events").exists(),
                         "the read-only mailbox must not create review audit writes")


    def test_work_record_backdated_capture_edit_and_task_history_protection(self):
        page = self._open_browser(open_detail=False)
        original_task_event = self.data_dir / "events" / "evt_v201-chromium-create-001.json"
        original_bytes = original_task_event.read_bytes()

        page.locator("#open-create-record").click()
        expect(page.locator("#page-worklog h1")).to_have_text("工作记录")
        page.locator("#work-record-content").fill("虚构的临时采购交期沟通")
        page.locator("#work-record-date").fill("2026-10-29")
        page.locator("#work-record-outcome").fill("交期已经确认")
        page.locator("#work-record-minutes").fill("40")
        page.locator("#work-record-task").select_option(self.task_id)
        page.locator("#work-record-submit").click()
        expect(page.locator("#work-record-message")).to_contain_text("已保存工作记录", timeout=10000)
        expect(page.locator(".work-entry-content")).to_contain_text("虚构的临时采购交期沟通")
        expect(page.locator(".work-entry-date")).to_have_text("2026-10-29")
        self.assertIn("1 条工作记录", page.locator("#work-record-count").inner_text())
        self.assertEqual(original_task_event.read_bytes(), original_bytes)
        directory = self.data_dir / "work_archive" / "record_events"
        files = sorted(directory.glob("*.json"))
        self.assertEqual(len(files), 1)
        first_event = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertNotIn("status", first_event["changes"])
        self.assertEqual(first_event["changes"]["occurred_on"], "2026-10-29")
        self.assertEqual(first_event["changes"]["task_id"], self.task_id)
        first_bytes = files[0].read_bytes()
        short_code = page.locator(".work-entry-meta span").first.inner_text()

        page.locator(".work-entry-footer button").first.click()
        expect(page.locator("#work-record-submit")).to_have_text("保存修改")
        page.locator("#work-record-content").fill("修正后的虚构交期沟通内容")
        page.locator("#work-record-date").fill("2026-10-28")
        page.locator("#work-record-submit").click()
        expect(page.locator("#work-record-message")).to_contain_text("已保存工作记录", timeout=10000)
        expect(page.locator(".work-entry-content")).to_contain_text("修正后的虚构交期沟通内容")
        expect(page.locator(".work-entry-date")).to_have_text("2026-10-28")
        self.assertEqual(short_code, page.locator(".work-entry-meta span").first.inner_text(),
                         "correcting work occurrence must never change its record code")
        self.assertEqual(len(list(directory.glob("*.json"))), 2)
        self.assertEqual(files[0].read_bytes(), first_bytes, "original record must remain byte-for-byte")
        self.assertEqual(original_task_event.read_bytes(), original_bytes)
