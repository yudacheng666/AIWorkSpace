"""Recurring task safety tests. All events and dates are fictional, in temporary storage."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app


TASK_ID = "TASK-RECUR-001"


def record(event_id, revision, changes, *, done=False, confirmed_end=False):
    value = {
        "version": 1, "event_id": event_id, "task_id": TASK_ID,
        "action": "create" if revision == 0 else "update", "actor": "user",
        "timestamp": "2026-11-05T00:00:00Z", "base_revision": revision,
        "changes": changes,
    }
    if done:
        value["confirmed_done"] = True
    if confirmed_end:
        value["confirmed_end"] = True
    return value


def rule(unit="daily", interval=1, start="2026-11-01", enabled=True):
    return {"unit": unit, "interval": interval, "start_date": start, "enabled": enabled}


class CycleMathTests(unittest.TestCase):
    def test_month_end_is_anchored_not_drifting(self):
        cycle = rule("monthly", 1, "2026-01-31")
        self.assertEqual(app.recurrence_bounds(cycle, date(2026, 2, 27)),
                         ("2026-01-31", "2026-02-27"))
        self.assertEqual(app.recurrence_bounds(cycle, date(2026, 2, 28)),
                         ("2026-02-28", "2026-03-30"))
        self.assertEqual(app.recurrence_bounds(cycle, date(2026, 3, 31)),
                         ("2026-03-31", "2026-04-29"))

    def test_leap_day_yearly_and_two_week_intervals(self):
        self.assertEqual(app.recurrence_bounds(rule("yearly", 1, "2024-02-29"),
                                               date(2025, 2, 28)),
                         ("2025-02-28", "2026-02-27"))
        self.assertEqual(app.recurrence_bounds(rule("weekly", 2, "2026-11-02"),
                                               date(2026, 11, 15)),
                         ("2026-11-02", "2026-11-15"))
        self.assertEqual(app.recurrence_bounds(rule("weekly", 2, "2026-11-02"),
                                               date(2026, 11, 16))[0], "2026-11-16")
        self.assertIsNone(app.recurrence_bounds(rule(start="2027-01-01"),
                                                date(2026, 12, 31)))

    def test_validation_blocks_invalid_and_unconfirmed_end(self):
        for bad in [
            {"unit": "bad", "interval": 1, "start_date": "2026-01-01", "enabled": True},
            rule(interval=0), rule(interval=True), rule(start="2026-02-30"),
            {**rule(), "enabled": "false"}, {**rule(), "extra": 9},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                app.validate_recurrence(bad)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            app.validate_event(record("rec-unconfirmed-0001", 1,
                                      {"recurrence": rule(enabled=False)}))
        with self.assertRaisesRegex(ValueError, "status"):
            app.validate_event(record("rec-unpaired-0001", 1,
                                      {"recurrence_status_period": "2026-11-01"}))


class RecurrenceReducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.start = date.today().isoformat()
        app.append_event(self.data_dir, record("rec-create-0001", 0, {
            "title": "虚构循环测试", "status": "todo",
            "recurrence": rule(start=self.start),
        }))

    def tearDown(self):
        self.temp.cleanup()

    def test_completed_cycle_automatically_reopens_without_writing_history(self):
        app.append_event(self.data_dir, record("rec-done-0001", 1, {
            "status": "done", "recurrence_status_period": self.start,
        }, done=True))
        current = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertEqual(current["status"], "done")
        self.assertTrue(current["recurrence_active"])
        self.assertEqual(current["revision"], 2)
        originals = {p.name: p.read_bytes() for p in (self.data_dir / "events").glob("*.json")}
        future = dict(current)
        app.project_recurrence([future], [], date.today() + timedelta(days=1))
        self.assertEqual(future["status"], "todo")
        self.assertEqual(future["manual_status"], "done")
        self.assertEqual(future["revision"], 2)
        self.assertEqual(originals,
                         {p.name: p.read_bytes() for p in (self.data_dir / "events").glob("*.json")})

    def test_stopped_cycle_stays_ended_then_reactivation_reopens(self):
        app.append_event(self.data_dir, record("rec-stop-0001", 1,
                         {"recurrence": rule(start=self.start, enabled=False)},
                         confirmed_end=True))
        stopped = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(stopped["recurrence_ended"])
        self.assertEqual(stopped["status"], "done")
        later = dict(stopped)
        app.project_recurrence([later], [], date.today() + timedelta(days=200))
        self.assertTrue(later["recurrence_ended"])
        self.assertEqual(later["status"], "done")
        app.append_event(self.data_dir, record("rec-resume-0001", 2,
                         {"recurrence": rule(start=self.start),
                          "status": "todo", "recurrence_status_period": None}))
        resumed = app.read_workspace(self.data_dir)["tasks"][0]
        self.assertTrue(resumed["recurrence_active"])
        self.assertFalse(resumed["recurrence_ended"])
        self.assertEqual(resumed["status"], "todo")
        self.assertEqual(resumed["revision"], 3)


class RecurrenceServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        app.append_event(self.data_dir, record("server-create-0001", 0,
                         {"title": "虚构周期任务", "status": "todo"}))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_factory(self.data_dir))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def post(self, path, payload):
        request = Request(self.base + path, data=json.dumps(payload).encode(),
                          method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def task(self):
        return app.read_workspace(self.data_dir)["tasks"][0]

    def test_configure_finish_end_resume_and_stale_revision(self):
        path = "/api/tasks/" + TASK_ID
        today = date.today().isoformat()
        config = {"action": "configure", "revision": 1,
                  "recurrence": rule(start=today)}
        status, _ = self.post(path + "/recurrence", config)
        self.assertEqual(status, 200)
        self.assertEqual(self.task()["revision"], 2)
        self.assertEqual(self.post(path + "/recurrence", config)[0], 409)
        self.assertEqual(self.post(path + "/update", {
            "title": "虚构周期任务", "status": "done", "revision": 2})[0], 400)
        self.assertEqual(self.post(path + "/update", {
            "title": "虚构周期任务", "status": "done", "revision": 2,
            "confirmed_done": True})[0], 200)
        self.assertEqual(self.task()["recurrence_status_period"], today)
        self.assertEqual(self.task()["status"], "done")
        self.assertEqual(self.post(path + "/recurrence", {
            "action": "end", "revision": 3, "confirmed": False})[0], 400)
        self.assertEqual(self.post(path + "/recurrence", {
            "action": "end", "revision": 3, "confirmed": True})[0], 200)
        self.assertTrue(self.task()["recurrence_ended"])
        self.assertEqual(self.post(path + "/update", {
            "title": "虚构周期任务", "status": "doing", "revision": 4})[0], 409)
        self.assertEqual(self.post(path + "/recurrence", {
            "action": "resume", "revision": 4, "confirmed": True})[0], 200)
        self.assertTrue(self.task()["recurrence_active"])
        self.assertEqual(self.task()["status"], "todo")
        self.assertEqual(self.task()["revision"], 5)

    def test_done_can_be_saved_again_when_old_period_manual_status_is_done(self):
        old = (date.today() - timedelta(days=1)).isoformat()
        path = "/api/tasks/" + TASK_ID
        app.append_event(self.data_dir, record("older-config-0001", 1,
                         {"recurrence": rule(start=old), "status": "todo",
                          "recurrence_status_period": None}))
        app.append_event(self.data_dir, record("older-done-0001", 2,
                         {"status": "done", "recurrence_status_period": old}, done=True))
        task = self.task()
        self.assertEqual(task["status"], "todo")
        self.assertEqual(task["manual_status"], "done")
        result, _ = self.post(path + "/update", {"title": "虚构周期任务",
                                "status": "done", "revision": 3, "confirmed_done": True})
        self.assertEqual(result, 200)
        self.assertEqual(self.task()["status"], "done")
        self.assertEqual(self.task()["recurrence_status_period"], date.today().isoformat())

    def test_steps_and_children_not_allowed_on_recurrent_parent(self):
        path = "/api/tasks/" + TASK_ID
        self.assertEqual(self.post(path + "/recurrence", {
            "action": "configure", "revision": 1,
            "recurrence": rule(start=date.today().isoformat())})[0], 200)
        self.assertEqual(self.post(path + "/steps", {"title": "不允许的下级步骤"})[0], 409)
        self.assertEqual(self.post("/api/tasks", {
            "title": "不允许的子任务", "parent_task_id": TASK_ID})[0], 400)
        self.assertEqual(self.task()["revision"], 2)

    def test_existing_step_prevents_recurring_configuration(self):
        path = "/api/tasks/" + TASK_ID
        self.assertEqual(self.post(path + "/steps", {"title": "已有步骤"})[0], 201)
        self.assertEqual(self.post(path + "/recurrence", {
            "action": "configure", "revision": 1,
            "recurrence": rule(start=date.today().isoformat())})[0], 409)
        self.assertIsNone(self.task()["recurrence"])
        self.assertEqual(self.task()["revision"], 1)


if __name__ == "__main__":
    unittest.main()
