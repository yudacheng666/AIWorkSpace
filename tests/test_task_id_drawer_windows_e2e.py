"""Isolated real Chromium regression for V2.0.1 task IDs and drawer behavior.

Only runs in the existing GitHub-hosted Windows Playwright job. All records
are fictional and live in a disposable temporary data directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import append_event, handler_factory, read_workspace  # noqa: E402


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

    def _open_browser(self):
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
        page.locator(".task-summary .task-open").first.click()
        self.assertFalse(page.locator("#task-detail-drawer").evaluate("(e) => e.hidden"))
        return page

    def test_short_id_copy_and_backdrop(self):
        page = self._open_browser()
        self.assertEqual(page.locator(".task-summary-id").first.inner_text(), self.short_id)
        self.assertEqual(page.locator("#task-detail-id").inner_text(), self.short_id)

        page.locator("#task-id-copy").click()
        page.wait_for_function(
            "document.querySelector('#task-id-feedback').textContent === '已复制'"
        )
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
