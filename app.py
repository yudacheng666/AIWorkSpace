"""Small local AIWorkSpace server; no external dependencies or credentials.

Put this file next to ``web/index.html``. Set ``--data-dir`` to a folder that
Google Drive for desktop synchronizes, or omit it for isolated demo data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from updater import (UpdateError, check_latest_update, get_install_status,
                     launch_update_helper, prepare_update, remove_stage)


ROOT = Path(__file__).resolve().parent
TASK_ID = re.compile(r"^TASK-[A-Za-z0-9-]{1,50}$")
PROJECT_ID = re.compile(r"^PROJECT-[A-F0-9]{32}$")
STEP_ID = re.compile(r"^STEP-[A-F0-9]{32}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9-]{8,80}$")
STATUSES = {"todo", "doing", "blocked", "done"}
PRIORITIES = {"low", "normal", "high", "urgent"}
DATE_FIELDS = ("due_date", "planned_date", "follow_up_date")
TASK_MANAGEMENT_FIELDS = ("owner", "priority", *DATE_FIELDS)
TASK_DEFAULTS = {"owner": None, "priority": "normal",
                 "due_date": None, "planned_date": None, "follow_up_date": None}
MAX_BODY = 16_384
MAX_ARCHIVE_BODY = 128_000
MAX_STEPS_PER_TASK = 100
WORK_RECORD_ID = re.compile(r"^RECORD-[A-F0-9]{32}$")
WORK_INBOX_ID = re.compile(r"^INBOX-[A-F0-9]{32}$")
WORK_CATEGORIES = {"meeting", "communication", "decision", "problem", "action",
                   "result", "idea", "other"}
WORK_RECORD_DEFAULTS = {
    "occurred_at": None, "category": "other", "project_id": None,
    "source_ids": [], "evidence_refs": [], "action_links": [],
}
_write_lock = threading.Lock()
_update_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_event(value: object) -> dict:
    """Validate both remote ChatGPT files and locally generated events."""
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("version must be 1")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid event_id")
    if not isinstance(value.get("task_id"), str) or not TASK_ID.fullmatch(value["task_id"]):
        raise ValueError("invalid task_id")
    if value.get("action") not in {"create", "update"}:
        raise ValueError("invalid action")
    if value.get("actor") not in {"chatgpt", "user"}:
        raise ValueError("invalid actor")
    revision = value.get("base_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid base_revision")
    changes = value.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("changes must be a nonempty object")
    if set(changes) - {"title", "status", "project_id", "related_project_ids", *TASK_MANAGEMENT_FIELDS}:
        raise ValueError("unknown fields")
    if "title" in changes and (not isinstance(changes["title"], str)
                               or not 1 <= len(changes["title"].strip()) <= 200):
        raise ValueError("title must be 1–200 characters")
    if "status" in changes and changes["status"] not in STATUSES:
        raise ValueError("invalid status")
    if "project_id" in changes and changes["project_id"] is not None:
        if not isinstance(changes["project_id"], str) or not PROJECT_ID.fullmatch(changes["project_id"]):
            raise ValueError("invalid project_id")
    if "related_project_ids" in changes:
        related = changes["related_project_ids"]
        if (not isinstance(related, list) or len(related) > 20
                or any(not isinstance(item, str) or not PROJECT_ID.fullmatch(item) for item in related)
                or len(set(related)) != len(related)):
            raise ValueError("invalid related_project_ids")
        if changes.get("project_id") in related:
            raise ValueError("primary project cannot also be a related project")
    # Dates are local calendar dates, not timestamps; keep the three meanings separate.
    if "owner" in changes:
        owner = changes["owner"]
        if owner is not None and (not isinstance(owner, str)
                                  or not 1 <= len(owner.strip()) <= 100):
            raise ValueError("owner must be null or 1–100 characters")
    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise ValueError("invalid priority")
    for field in DATE_FIELDS:
        if field in changes and changes[field] is not None:
            value_date = changes[field]
            if not isinstance(value_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value_date):
                raise ValueError(f"invalid {field} (YYYY-MM-DD required)")
            try:
                date.fromisoformat(value_date)
            except ValueError as exc:
                raise ValueError(f"invalid {field} calendar date") from exc
    if value["action"] == "create":
        if revision != 0 or "title" not in changes or changes.get("status", "todo") != "todo":
            raise ValueError("create must start with title and todo status")
    if value["action"] == "update" and revision == 0:
        raise ValueError("update must refer to an existing revision")
    if changes.get("status") == "done" and (
        value["actor"] != "user" or value.get("confirmed_done") is not True
    ):
        raise ValueError("only an explicitly confirmed user action can complete a task")
    return value


def normalized_task_fields(payload: dict) -> dict:
    """Normalize only supplied task management values; omission means unchanged."""
    changes = {}
    for field in TASK_MANAGEMENT_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field == "owner" and isinstance(value, str):
            value = value.strip() or None
        if field in DATE_FIELDS and value == "":
            # Empty web date inputs explicitly clear dates. The event stores null.
            value = None
        changes[field] = value
    return changes


def validate_project_event(value: object) -> dict:
    """Validate append-only project create/update events."""
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("version must be 1")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid event_id")
    if not isinstance(value.get("project_id"), str) or not PROJECT_ID.fullmatch(value["project_id"]):
        raise ValueError("invalid project_id")
    if value.get("action") not in {"create", "update"}:
        raise ValueError("invalid action")
    if value.get("actor") not in {"chatgpt", "user"}:
        raise ValueError("invalid actor")
    revision = value.get("base_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid base_revision")
    changes = value.get("changes")
    if not isinstance(changes, dict) or set(changes) != {"name"}:
        raise ValueError("project changes must contain only name")
    name = changes["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError("project name must be 1–120 characters")
    if value["action"] == "create" and revision != 0:
        raise ValueError("project create must use revision 0")
    if value["action"] == "update" and revision < 1:
        raise ValueError("project update must refer to an existing revision")
    return value


def validate_step_event(value: object) -> dict:
    """Validate append-only execution-step and per-task ordering events."""
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("version must be 1")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid event_id")
    if not isinstance(value.get("task_id"), str) or not TASK_ID.fullmatch(value["task_id"]):
        raise ValueError("invalid task_id")
    if value.get("action") not in {"create", "update", "reorder"}:
        raise ValueError("invalid step action")
    if value.get("actor") not in {"chatgpt", "user"}:
        raise ValueError("invalid actor")
    revision = value.get("base_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid base_revision")
    changes = value.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("changes must be a nonempty object")
    if value["action"] == "reorder":
        if set(value) - {"version", "event_id", "task_id", "action", "actor",
                         "timestamp", "base_revision", "changes"}:
            raise ValueError("unknown step-order event fields")
        if set(changes) != {"step_ids"}:
            raise ValueError("step-order changes must contain only step_ids")
        step_ids = changes["step_ids"]
        if (not isinstance(step_ids, list) or not 1 <= len(step_ids) <= MAX_STEPS_PER_TASK
                or any(not isinstance(item, str) or not STEP_ID.fullmatch(item) for item in step_ids)
                or len(set(step_ids)) != len(step_ids)):
            raise ValueError("invalid step_ids")
        return value
    if set(value) - {"version", "event_id", "task_id", "step_id", "action", "actor",
                     "timestamp", "base_revision", "changes", "confirmed_done"}:
        raise ValueError("unknown step event fields")
    if not isinstance(value.get("step_id"), str) or not STEP_ID.fullmatch(value["step_id"]):
        raise ValueError("invalid step_id")
    if set(changes) - {"title", "status", "position"}:
        raise ValueError("unknown step fields")
    if "title" in changes and (not isinstance(changes["title"], str)
                               or not 1 <= len(changes["title"].strip()) <= 200):
        raise ValueError("step title must be 1–200 characters")
    if "status" in changes and changes["status"] not in STATUSES:
        raise ValueError("invalid step status")
    if "position" in changes and (
        type(changes["position"]) is not int or
        not 1 <= changes["position"] <= MAX_STEPS_PER_TASK
    ):
        raise ValueError("invalid step position")
    if value["action"] == "create":
        if revision != 0 or set(changes) != {"title", "position"}:
            raise ValueError("step create requires title, position and revision 0")
    elif revision < 1 or "position" in changes:
        raise ValueError("step update must refer to an existing revision and cannot set position")
    if changes.get("status") == "done" and (
        value["actor"] != "user" or value.get("confirmed_done") is not True
    ):
        raise ValueError("step completion needs explicit user confirmation")
    if value.get("confirmed_done") is True and changes.get("status") != "done":
        raise ValueError("confirmed_done is only valid when completing a step")
    return value


def summarize_conflict_events(events: list[dict]) -> list[dict]:
    """Return only the details needed to explain an unresolved conflict in the UI."""
    ordered = sorted(events, key=lambda event: (
        str(event.get("timestamp", "")), str(event.get("event_id", ""))
    ))
    return [
        {
            "event_id": event["event_id"],
            "timestamp": event.get("timestamp", ""),
            "actor": event["actor"],
            "changes": dict(event["changes"]),
        }
        for event in ordered
    ]


def conflicting_fields(events: list[dict]) -> list[str]:
    """Compare JSON values by content (arrays are not hashable in Python)."""
    fields = {field for event in events for field in event["changes"]}
    return sorted(
        field for field in fields
        if len({
            json.dumps(event["changes"].get(field), sort_keys=True, ensure_ascii=False)
            for event in events
        }) > 1
    )


def read_projects(data_dir: Path) -> dict:
    """Reduce append-only project events without overwriting project history."""
    directory = data_dir / "project_events"
    if not directory.exists():
        return {"projects": [], "warnings": []}
    created: dict[str, list[dict]] = defaultdict(list)
    updated: dict[str, list[dict]] = defaultdict(list)
    warnings: list[str] = []
    seen: dict[str, dict] = {}
    duplicate_conflicts: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(directory.glob("*.json")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BODY:
                raise ValueError("file too large")
            event = validate_project_event(json.loads(path.read_text(encoding="utf-8-sig")))
            previous = seen.get(event["event_id"])
            if previous is not None:
                if previous == event:
                    warnings.append(f"{path.name}: duplicate project event_id (identical; ignored)")
                    continue
                variants = duplicate_conflicts[event["event_id"]]
                if not variants:
                    variants.append(previous)
                if event not in variants:
                    variants.append(event)
                warnings.append(f"{path.name}: duplicate project event_id with conflicting content")
            else:
                seen[event["event_id"]] = event
            destination = created if event["action"] == "create" else updated
            destination[event["project_id"]].append(event)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            warnings.append(f"{path.name}: {exc}")

    projects: list[dict] = []
    for project_id in sorted(set(created) | set(updated)):
        roots = created[project_id]
        if len(roots) != 1:
            warnings.append(f"{project_id}: missing or multiple project creation events")
            candidates = roots or updated[project_id]
            projects.append({
                "project_id": project_id,
                "name": "项目创建记录冲突" if roots else "项目创建记录尚未同步",
                "revision": 0,
                "conflict": True,
                "conflict_candidates": summarize_conflict_events(candidates),
            })
            continue
        project = {"project_id": project_id, "name": roots[0]["changes"]["name"].strip(),
                   "revision": 1, "conflict": False, "conflict_candidates": []}
        by_revision: dict[int, list[dict]] = defaultdict(list)
        for event in updated[project_id]:
            by_revision[event["base_revision"]].append(event)
        while project["revision"] in by_revision:
            candidates = by_revision.pop(project["revision"])
            if len(candidates) != 1:
                project["conflict"] = True
                project["conflict_candidates"] = summarize_conflict_events(candidates)
                warnings.append(f"{project_id}: conflicting project edits at revision {project['revision']}")
                break
            project["name"] = candidates[0]["changes"]["name"].strip()
            project["revision"] += 1
        if by_revision:
            remaining = [event for group in by_revision.values() for event in group]
            project["conflict"] = True
            project["conflict_candidates"].extend(summarize_conflict_events(remaining))
            warnings.append(f"{project_id}: unresolved or out-of-order project edits")
        projects.append(project)

    by_id = {project["project_id"]: project for project in projects}
    for event_id, variants in duplicate_conflicts.items():
        affected = {event["project_id"] for event in variants}
        for project_id in affected:
            project = by_id.get(project_id)
            if project:
                project["conflict"] = True
                project["conflict_candidates"].extend(summarize_conflict_events(
                    [event for event in variants if event["project_id"] == project_id]
                ))
                warnings.append(f"{project_id}: project event_id {event_id} needs review")
    projects.sort(key=lambda project: (project["name"].casefold(), project["project_id"]))
    return {"projects": projects, "warnings": warnings}


def read_steps(data_dir: Path, tasks: list[dict], warnings: list[str]) -> None:
    """Attach ordered, independently versioned steps to tasks without rewriting history."""
    directory = data_dir / "step_events"
    by_step: dict[str, list[dict]] = defaultdict(list)
    by_task_order: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, dict] = {}
    duplicate_conflicts: dict[str, list[dict]] = defaultdict(list)
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_BODY:
                    raise ValueError("file too large")
                event = validate_step_event(json.loads(path.read_text(encoding="utf-8-sig")))
                previous = seen.get(event["event_id"])
                if previous is not None:
                    if previous == event:
                        warnings.append(f"{path.name}: duplicate step event_id (identical; ignored)")
                        continue
                    variants = duplicate_conflicts[event["event_id"]]
                    if not variants:
                        variants.append(previous)
                    if event not in variants:
                        variants.append(event)
                    warnings.append(f"{path.name}: duplicate step event_id with conflicting content")
                else:
                    seen[event["event_id"]] = event
                if event["action"] == "reorder":
                    by_task_order[event["task_id"]].append(event)
                else:
                    by_step[event["step_id"]].append(event)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                warnings.append(f"{path.name}: {exc}")

    steps_by_task: dict[str, list[dict]] = defaultdict(list)
    steps_by_id: dict[str, dict] = {}
    for step_id, events in by_step.items():
        roots = [event for event in events if event["action"] == "create"]
        task_ids = {event["task_id"] for event in events}
        if len(roots) != 1:
            warnings.append(f"{step_id}: missing or multiple step creation events")
            if not roots:
                continue
            root = roots[0]
            for task_id in sorted({event["task_id"] for event in roots}):
                task_root = next(event for event in roots if event["task_id"] == task_id)
                placeholder = {
                    "task_id": task_id, "step_id": step_id,
                    "title": "步骤创建记录冲突", "status": "todo", "revision": 0,
                    "conflict": True, "conflict_fields": ["title", "task_id"],
                    "conflict_candidates": summarize_conflict_events(roots),
                    "created_at": task_root.get("timestamp", ""),
                    "created_position": task_root["changes"].get("position"),
                }
                steps_by_task[task_id].append(placeholder)
                steps_by_id.setdefault(step_id, placeholder)
            continue
        else:
            root = roots[0]
            step = {
                "task_id": root["task_id"], "step_id": step_id,
                "title": root["changes"]["title"].strip(), "status": "todo",
                "revision": 1, "conflict": False,
                "conflict_fields": [], "conflict_candidates": [],
                "created_at": root.get("timestamp", ""),
                "created_position": root["changes"].get("position"),
            }
            if len(task_ids) != 1:
                step["conflict"] = True
                step["conflict_fields"] = ["task_id"]
                step["conflict_candidates"] = summarize_conflict_events(events)
                warnings.append(f"{step_id}: events reference different parent tasks")
            updates: dict[int, list[dict]] = defaultdict(list)
            for event in events:
                if event["action"] == "update":
                    updates[event["base_revision"]].append(event)
            while step["revision"] in updates:
                candidates = updates.pop(step["revision"])
                if len(candidates) != 1:
                    step["conflict"] = True
                    step["conflict_fields"] = sorted(
                        set(step["conflict_fields"]) |
                        {field for event in candidates for field in event["changes"]}
                    )
                    step["conflict_candidates"].extend(summarize_conflict_events(candidates))
                    warnings.append(f"{step_id}: conflicting edits at revision {step['revision']}")
                    break
                step.update(candidates[0]["changes"])
                if "title" in step:
                    step["title"] = step["title"].strip()
                step["revision"] += 1
            if updates:
                remaining = [event for group in updates.values() for event in group]
                step["conflict"] = True
                step["conflict_fields"] = sorted(
                    set(step["conflict_fields"]) |
                    {field for event in remaining for field in event["changes"]}
                )
                step["conflict_candidates"].extend(summarize_conflict_events(remaining))
                warnings.append(f"{step_id}: unresolved or out-of-order step edits")
        steps_by_id[step_id] = step
        steps_by_task[step["task_id"]].append(step)

    # A reused event ID with different content freezes each affected step/order stream.
    duplicate_order_conflicts: dict[str, list[dict]] = defaultdict(list)
    for event_id, variants in duplicate_conflicts.items():
        affected_steps = {event["step_id"] for event in variants if event["action"] != "reorder"}
        for step_id in affected_steps:
            step = steps_by_id.get(step_id)
            if step:
                step["conflict"] = True
                step["conflict_fields"] = sorted(
                    set(step["conflict_fields"]) | {"event_id"}
                )
                step["conflict_candidates"].extend(summarize_conflict_events(
                    [event for event in variants if event.get("step_id") == step_id]
                ))
                warnings.append(f"{step_id}: event_id {event_id} has conflicting content")
        for task_id in {event["task_id"] for event in variants if event["action"] == "reorder"}:
            warnings.append(f"{task_id}: step-order event_id {event_id} has conflicting content")
            duplicate_order_conflicts[task_id].extend(variants)

    task_by_id = {task["task_id"]: task for task in tasks}
    for task_id, steps in steps_by_task.items():
        if task_id not in task_by_id:
            warnings.append(f"{task_id}: step records are waiting for the parent task to sync")
    for task in tasks:
        task_id = task["task_id"]
        defaults = sorted(steps_by_task.get(task_id, []),
                          key=lambda step: (
                              0 if type(step.get("created_position")) is int else 1,
                              step.get("created_position") if type(step.get("created_position")) is int else 0,
                              str(step.get("created_at", "")), step["step_id"]))
        order_revision = 0
        order_ids: list[str] = []
        duplicate_order_variants = duplicate_order_conflicts.get(task_id, [])
        duplicate_order_ids = {
            event["event_id"] for event in duplicate_order_variants
            if event["action"] == "reorder" and event["task_id"] == task_id
        }
        duplicate_order_revisions = {
            event["base_revision"] for event in duplicate_order_variants
            if event["action"] == "reorder" and event["task_id"] == task_id
        }
        order_conflict = bool(duplicate_order_ids)
        order_candidates: list[dict] = (
            summarize_conflict_events(duplicate_order_variants)
            if duplicate_order_variants else []
        )
        order_updates: dict[int, list[dict]] = defaultdict(list)
        for event in by_task_order.get(task_id, []):
            order_updates[event["base_revision"]].append(event)
        while order_revision in order_updates:
            # Do not apply any event at a revision implicated in an event-ID collision.
            # Keep the last unambiguous prefix and expose all colliding variants as candidates.
            if order_revision in duplicate_order_revisions:
                warnings.append(
                    f"{task_id}: step-order event_id collision at revision {order_revision}"
                )
                break
            candidates = order_updates.pop(order_revision)
            if len(candidates) != 1:
                order_conflict = True
                order_candidates.extend(summarize_conflict_events(candidates))
                warnings.append(f"{task_id}: conflicting step order at revision {order_revision}")
                break
            candidate_ids = list(candidates[0]["changes"]["step_ids"])
            foreign_ids = [
                step_id for step_id in candidate_ids
                if step_id in steps_by_id and steps_by_id[step_id]["task_id"] != task_id
            ]
            if foreign_ids:
                order_conflict = True
                order_candidates.extend(summarize_conflict_events(candidates))
                warnings.append(f"{task_id}: step order references steps belonging to another task")
                break
            order_ids = candidate_ids
            order_revision += 1
        if order_updates:
            order_conflict = True
            remaining = [
                event for group in order_updates.values() for event in group
                if event["event_id"] not in duplicate_order_ids
            ]
            if remaining:
                order_candidates.extend(summarize_conflict_events(remaining))
            warnings.append(f"{task_id}: unresolved or out-of-order step order")
        known = {step["step_id"]: step for step in defaults}
        missing_order_ids = [step_id for step_id in order_ids if step_id not in known]
        if missing_order_ids:
            warnings.append(
                f"{task_id}: step order references {len(missing_order_ids)} step(s) "
                "whose creation events have not synced"
            )
        ordered = [known[step_id] for step_id in order_ids if step_id in known]
        ordered_ids = {step["step_id"] for step in ordered}
        ordered.extend(step for step in defaults if step["step_id"] not in ordered_ids)
        for index, step in enumerate(ordered, start=1):
            step["position"] = index
        task["steps"] = ordered
        task["step_order_revision"] = order_revision
        task["step_order_conflict"] = order_conflict
        task["step_order_incomplete"] = bool(missing_order_ids)
        task["step_order_missing_ids"] = missing_order_ids
        task["step_order_candidates"] = order_candidates


def read_workspace(data_dir: Path) -> dict:
    """Reduce independent event files; never silently choose a concurrent edit."""
    event_dir = data_dir / "events"
    created: dict[str, list[dict]] = defaultdict(list)
    updated: dict[str, list[dict]] = defaultdict(list)
    warnings: list[str] = []
    seen: dict[str, dict] = {}
    duplicate_conflicts: dict[str, list[dict]] = defaultdict(list)
    project_state = read_projects(data_dir)
    if not event_dir.exists():
        tasks: list[dict] = []
        warnings.extend(project_state["warnings"])
        read_steps(data_dir, tasks, warnings)
        return {"tasks": tasks, "projects": project_state["projects"], "warnings": warnings}

    for path in sorted(event_dir.glob("*.json")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BODY:
                raise ValueError("file too large")
            event = validate_event(json.loads(path.read_text(encoding="utf-8-sig")))
            previous = seen.get(event["event_id"])
            if previous is not None:
                if previous == event:
                    warnings.append(f"{path.name}: duplicate event_id (identical event; ignored)")
                    continue
                warnings.append(f"{path.name}: duplicate event_id with conflicting content; needs review")
                variants = duplicate_conflicts[event["event_id"]]
                if not variants:
                    variants.append(previous)
                if event not in variants:
                    variants.append(event)
            else:
                seen[event["event_id"]] = event
            destination = created if event["action"] == "create" else updated
            destination[event["task_id"]].append(event)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            warnings.append(f"{path.name}: {exc}")

    tasks: list[dict] = []
    for task_id in sorted(set(created) | set(updated)):
        roots = created[task_id]
        if not roots:
            warnings.append(f"{task_id}: waiting for task creation file")
            continue
        if len(roots) != 1:
            root_candidates = summarize_conflict_events(roots)
            root_fields = conflicting_fields(roots)
            warnings.append(f"{task_id}: multiple creation events; needs review")
            tasks.append({
                "task_id": task_id,
                "title": "创建记录冲突" if "title" in root_fields else roots[0]["changes"]["title"].strip(),
                "status": "todo",
                "revision": 0,
                "conflict": True,
                "conflict_fields": root_fields,
                "conflict_candidates": root_candidates,
            })
            continue
        task = {"task_id": task_id, **roots[0]["changes"],
                "title": roots[0]["changes"]["title"].strip(),
                "status": roots[0]["changes"].get("status", "todo"),
                "revision": 1, "conflict": False,
                "conflict_fields": [], "conflict_candidates": []}
        by_revision: dict[int, list[dict]] = defaultdict(list)
        for event in updated[task_id]:
            by_revision[event["base_revision"]].append(event)

        while task["revision"] in by_revision:
            candidates = by_revision.pop(task["revision"])
            if len(candidates) != 1:
                task["conflict"] = True
                task["conflict_fields"] = conflicting_fields(candidates)
                task["conflict_candidates"] = summarize_conflict_events(candidates)
                warnings.append(f"{task_id}: conflicting edits of revision {task['revision']}")
                break
            task.update(candidates[0]["changes"])
            task["title"] = task["title"].strip()
            task["revision"] += 1
        if by_revision:
            remaining = [event for group in by_revision.values() for event in group]
            task["conflict"] = True
            task["conflict_fields"] = sorted(
                set(task["conflict_fields"]) | set(conflicting_fields(remaining))
            )
            task["conflict_candidates"].extend(summarize_conflict_events(remaining))
            warnings.append(f"{task_id}: unresolved or out-of-order edits")
        tasks.append(task)

    # A repeated event ID with different content is not a harmless duplicate.
    # Freeze every affected task, even if the variants point at different task IDs
    # or different revisions and therefore would not collide in the reducer above.
    task_by_id = {task["task_id"]: task for task in tasks}
    for event_id, variants in duplicate_conflicts.items():
        by_task: dict[str, list[dict]] = defaultdict(list)
        for event in variants:
            by_task[event["task_id"]].append(event)
        for task_id, task_variants in by_task.items():
            task = task_by_id.get(task_id)
            if task is None:
                continue
            task["conflict"] = True
            task["conflict_fields"] = sorted(
                set(task.get("conflict_fields", [])) | set(conflicting_fields(task_variants))
            )
            existing = {
                (candidate.get("event_id"),
                 json.dumps(candidate.get("changes", {}), ensure_ascii=False, sort_keys=True))
                for candidate in task.get("conflict_candidates", [])
            }
            for candidate in summarize_conflict_events(task_variants):
                signature = (
                    candidate.get("event_id"),
                    json.dumps(candidate.get("changes", {}), ensure_ascii=False, sort_keys=True),
                )
                if signature not in existing:
                    task["conflict_candidates"].append(candidate)
                    existing.add(signature)
            warnings.append(f"{task_id}: event_id {event_id} has conflicting content; needs review")

    project_map = {project["project_id"]: project for project in project_state["projects"]}
    for task in tasks:
        for field, default in TASK_DEFAULTS.items():
            task.setdefault(field, default)
        task.setdefault("project_id", None)
        task.setdefault("related_project_ids", [])
        primary = project_map.get(task["project_id"]) if task["project_id"] else None
        task["project_name"] = primary["name"] if primary and not primary["conflict"] else None
        task["project_missing"] = bool(task["project_id"] and (primary is None or primary["conflict"]))
        related_names = []
        for project_id in task["related_project_ids"]:
            related = project_map.get(project_id)
            if related and not related["conflict"]:
                related_names.append(related["name"])
            else:
                task["project_missing"] = True
        task["related_project_names"] = related_names
        if task["project_missing"]:
            warnings.append(f"{task['task_id']}: referenced project has not synced or is unavailable")
    read_steps(data_dir, tasks, warnings)
    warnings.extend(project_state["warnings"])
    return {"tasks": tasks, "projects": project_state["projects"], "warnings": warnings}


def _append_json_event(data_dir: Path, event: dict, folder: str) -> Path:
    """Publish one complete JSON file atomically; never replace an existing event."""
    directory = data_dir / folder
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"evt_{event['event_id']}.json"
    if destination.exists():
        raise FileExistsError("event already exists")
    payload = json.dumps(event, ensure_ascii=False, indent=2) + "\n"
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".part",
                                         prefix=".pending-", dir=directory,
                                         delete=False) as stream:
            temp_name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp_name, destination)
        except FileExistsError:
            raise FileExistsError("event already exists") from None
        published_temp = temp_name
        temp_name = None
        try:
            os.unlink(published_temp)
        except OSError:
            pass
        return destination
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def append_event(data_dir: Path, event: dict) -> Path:
    validate_event(event)
    return _append_json_event(data_dir, event, "events")


def append_project_event(data_dir: Path, event: dict) -> Path:
    validate_project_event(event)
    return _append_json_event(data_dir, event, "project_events")


def append_step_event(data_dir: Path, event: dict) -> Path:
    validate_step_event(event)
    return _append_json_event(data_dir, event, "step_events")




def validate_optional_datetime(value: object, field: str) -> None:
    """Accept a local calendar date or an ISO timestamp with an explicit offset."""
    if value is None:
        return
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"invalid {field}")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            date.fromisoformat(value)
            return
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone offset required")
    except ValueError as exc:
        raise ValueError(f"invalid {field} (use YYYY-MM-DD or ISO timestamp with timezone)") from exc


def validate_evidence_refs(value: object) -> list[dict]:
    """Validate lightweight references; file bytes and private URLs never enter the event."""
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError("evidence_refs must be a list of at most 20 items")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"file_id", "name", "mime_type"}:
            raise ValueError("invalid evidence reference")
        file_id = item.get("file_id")
        name = item.get("name")
        mime_type = item.get("mime_type")
        if not isinstance(file_id, str) or not 1 <= len(file_id.strip()) <= 256:
            raise ValueError("evidence file_id must be 1–256 characters")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
            raise ValueError("evidence name must be 1–200 characters")
        if mime_type is not None and (
            not isinstance(mime_type, str) or not 1 <= len(mime_type.strip()) <= 100
        ):
            raise ValueError("invalid evidence mime_type")
        reference = {"file_id": file_id.strip(), "name": name.strip()}
        if mime_type is not None:
            reference["mime_type"] = mime_type.strip()
        result.append(reference)
    return result


def validate_action_links(value: object) -> list[dict]:
    """Validate references from a work record to existing task/step identifiers."""
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("action_links must be a list of at most 50 items")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"target_type", "target_id", "relation"}:
            raise ValueError("invalid action link")
        target_type = item["target_type"]
        target_id = item["target_id"]
        relation = item["relation"]
        if target_type == "task":
            valid_target = isinstance(target_id, str) and bool(TASK_ID.fullmatch(target_id))
        elif target_type == "step":
            valid_target = isinstance(target_id, str) and bool(STEP_ID.fullmatch(target_id))
        else:
            valid_target = False
        if not valid_target:
            raise ValueError("action link target must be a valid task or step ID")
        if relation not in {"derived_action", "progress_on", "result_of"}:
            raise ValueError("invalid action link relation")
        signature = (target_type, target_id, relation)
        if signature in seen:
            raise ValueError("duplicate action link")
        seen.add(signature)
        result.append({"target_type": target_type, "target_id": target_id, "relation": relation})
    return result


def validate_work_inbox_event(value: object) -> dict:
    """Validate immutable raw work input captured by the workbench or ChatGPT."""
    allowed = {
        "version", "event_id", "inbox_id", "action", "actor", "source",
        "captured_at", "occurred_at", "content", "evidence_refs", "capture_key",
    }
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("work inbox version must be 1")
    if set(value) - allowed:
        raise ValueError("unknown work inbox fields")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid work inbox event_id")
    if not isinstance(value.get("inbox_id"), str) or not WORK_INBOX_ID.fullmatch(value["inbox_id"]):
        raise ValueError("invalid inbox_id")
    if value.get("action") != "capture":
        raise ValueError("invalid work inbox action")
    if value.get("actor") not in {"user", "chatgpt"}:
        raise ValueError("invalid work inbox actor")
    if value.get("source") not in {"workbench", "chatgpt", "voice_transcript", "other"}:
        raise ValueError("invalid work inbox source")
    captured_at = value.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("captured_at is required")
    validate_optional_datetime(captured_at, "captured_at")
    if not isinstance(value.get("content"), str) or not 1 <= len(value["content"].strip()) <= 12_000:
        raise ValueError("work inbox content must be 1–12000 characters")
    validate_optional_datetime(value.get("occurred_at"), "occurred_at")
    if "evidence_refs" in value:
        validate_evidence_refs(value["evidence_refs"])
    if "capture_key" in value and (
        not isinstance(value["capture_key"], str) or
        not re.fullmatch(r"[A-Za-z0-9-]{8,80}", value["capture_key"])
    ):
        raise ValueError("invalid capture_key")
    return value


def validate_work_record_event(value: object) -> dict:
    """Validate append-only create/update events for a structured work record."""
    allowed = {
        "version", "event_id", "record_id", "action", "actor",
        "timestamp", "base_revision", "changes",
    }
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("work record version must be 1")
    if set(value) - allowed:
        raise ValueError("unknown work record event fields")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid work record event_id")
    if not isinstance(value.get("record_id"), str) or not WORK_RECORD_ID.fullmatch(value["record_id"]):
        raise ValueError("invalid record_id")
    if value.get("action") not in {"create", "update"}:
        raise ValueError("invalid work record action")
    if value.get("actor") not in {"user", "chatgpt"}:
        raise ValueError("invalid work record actor")
    revision = value.get("base_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid work record revision")
    changes = value.get("changes")
    allowed_changes = {
        "title", "summary", "occurred_at", "category", "project_id",
        "source_ids", "evidence_refs", "action_links",
    }
    if not isinstance(changes, dict) or not changes or set(changes) - allowed_changes:
        raise ValueError("invalid work record changes")
    if "title" in changes and (
        not isinstance(changes["title"], str) or not 1 <= len(changes["title"].strip()) <= 200
    ):
        raise ValueError("work record title must be 1–200 characters")
    if "summary" in changes and (
        not isinstance(changes["summary"], str) or not 1 <= len(changes["summary"].strip()) <= 12_000
    ):
        raise ValueError("work record summary must be 1–12000 characters")
    if "occurred_at" in changes:
        validate_optional_datetime(changes["occurred_at"], "occurred_at")
    if "category" in changes and changes["category"] not in WORK_CATEGORIES:
        raise ValueError("invalid work record category")
    if "project_id" in changes and changes["project_id"] is not None:
        if not isinstance(changes["project_id"], str) or not PROJECT_ID.fullmatch(changes["project_id"]):
            raise ValueError("invalid work record project_id")
    if "source_ids" in changes:
        source_ids = changes["source_ids"]
        if (not isinstance(source_ids, list) or len(source_ids) > 50
                or any(not isinstance(item, str) or not WORK_INBOX_ID.fullmatch(item) for item in source_ids)
                or len(set(source_ids)) != len(source_ids)):
            raise ValueError("invalid work record source_ids")
    if "evidence_refs" in changes:
        validate_evidence_refs(changes["evidence_refs"])
    if "action_links" in changes:
        validate_action_links(changes["action_links"])
    if value["action"] == "create":
        if revision != 0 or not {"title", "summary"}.issubset(changes):
            raise ValueError("work record create requires title, summary and revision 0")
    elif revision < 1:
        raise ValueError("work record update must refer to an existing revision")
    return value


def append_work_inbox_event(data_dir: Path, event: dict) -> Path:
    validate_work_inbox_event(event)
    return _append_json_event(data_dir, event, "work_archive/inbox")


def append_work_record_event(data_dir: Path, event: dict) -> Path:
    validate_work_record_event(event)
    return _append_json_event(data_dir, event, "work_archive/record_events")


def summarize_work_record_events(events: list[dict]) -> list[dict]:
    ordered = sorted(events, key=lambda event: (
        str(event.get("timestamp", "")), str(event.get("event_id", ""))
    ))
    return [{
        "event_id": event["event_id"],
        "timestamp": event.get("timestamp", ""),
        "actor": event["actor"],
        "changes": dict(event["changes"]),
    } for event in ordered]


def read_work_archive(data_dir: Path, workspace: dict | None = None) -> dict:
    """Read the additive work archive; an absent directory is a valid empty archive."""
    root = data_dir / "work_archive"
    warnings: list[str] = []
    inbox: list[dict] = []
    records: list[dict] = []
    if not root.exists():
        return {"inbox": inbox, "records": records, "warnings": warnings}

    inbox_dir = root / "inbox"
    seen_inbox_events: dict[str, dict] = {}
    seen_capture_keys: dict[str, dict] = {}
    if inbox_dir.is_dir():
        for path in sorted(inbox_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_ARCHIVE_BODY:
                    raise ValueError("file too large")
                event = validate_work_inbox_event(json.loads(path.read_text(encoding="utf-8-sig")))
                previous = seen_inbox_events.get(event["event_id"])
                if previous is not None:
                    if previous == event:
                        warnings.append(f"{path.name}: duplicate inbox event_id (identical; ignored)")
                    else:
                        warnings.append(f"{path.name}: inbox event_id has conflicting content")
                    continue
                capture_key = event.get("capture_key")
                if capture_key and capture_key in seen_capture_keys:
                    previous_capture = seen_capture_keys[capture_key]
                    same_capture = all(
                        previous_capture.get(field) == event.get(field)
                        for field in ("content", "occurred_at", "source", "evidence_refs")
                    )
                    if same_capture:
                        warnings.append(f"{path.name}: duplicate capture_key (identical; ignored)")
                    else:
                        warnings.append(f"{path.name}: capture_key has conflicting content")
                    continue
                seen_inbox_events[event["event_id"]] = event
                if capture_key:
                    seen_capture_keys[capture_key] = event
                inbox.append({
                    **event,
                    "status": "pending",
                    "linked_record_ids": [],
                })
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                warnings.append(f"{path.name}: {exc}")

    record_dir = root / "record_events"
    created: dict[str, list[dict]] = defaultdict(list)
    updated: dict[str, list[dict]] = defaultdict(list)
    seen_record_events: dict[str, dict] = {}
    duplicate_conflicts: dict[str, list[dict]] = defaultdict(list)
    if record_dir.is_dir():
        for path in sorted(record_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_ARCHIVE_BODY:
                    raise ValueError("file too large")
                event = validate_work_record_event(json.loads(path.read_text(encoding="utf-8-sig")))
                previous = seen_record_events.get(event["event_id"])
                if previous is not None:
                    if previous == event:
                        warnings.append(f"{path.name}: duplicate work record event_id (identical; ignored)")
                        continue
                    variants = duplicate_conflicts[event["event_id"]]
                    if not variants:
                        variants.append(previous)
                    if event not in variants:
                        variants.append(event)
                    warnings.append(f"{path.name}: work record event_id has conflicting content")
                else:
                    seen_record_events[event["event_id"]] = event
                destination = created if event["action"] == "create" else updated
                destination[event["record_id"]].append(event)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                warnings.append(f"{path.name}: {exc}")

    for record_id in sorted(set(created) | set(updated)):
        roots = created[record_id]
        if not roots:
            warnings.append(f"{record_id}: waiting for work record creation event")
            continue
        root_event = sorted(roots, key=lambda event: (
            str(event.get("timestamp", "")), str(event.get("event_id", ""))
        ))[0]
        changes = root_event["changes"]
        record = {
            "record_id": record_id,
            **WORK_RECORD_DEFAULTS,
            **changes,
            "revision": 1,
            "conflict": len(roots) != 1,
            "conflict_fields": [],
            "conflict_candidates": summarize_work_record_events(roots) if len(roots) != 1 else [],
            "created_at": root_event.get("timestamp", ""),
            "updated_at": root_event.get("timestamp", ""),
        }
        if len(roots) != 1:
            record["conflict_fields"] = sorted({
                field for event in roots for field in event["changes"]
            })
            warnings.append(f"{record_id}: multiple work record creation events; needs review")
        else:
            by_revision: dict[int, list[dict]] = defaultdict(list)
            for event in updated[record_id]:
                by_revision[event["base_revision"]].append(event)
            while record["revision"] in by_revision:
                candidates = by_revision.pop(record["revision"])
                if len(candidates) != 1:
                    record["conflict"] = True
                    record["conflict_fields"] = sorted({
                        field for event in candidates for field in event["changes"]
                    })
                    record["conflict_candidates"] = summarize_work_record_events(candidates)
                    warnings.append(f"{record_id}: conflicting work record edits at revision {record['revision']}")
                    break
                accepted = candidates[0]
                record.update(accepted["changes"])
                record["revision"] += 1
                record["updated_at"] = accepted.get("timestamp", record["updated_at"])
            if by_revision:
                remaining = [event for group in by_revision.values() for event in group]
                record["conflict"] = True
                record["conflict_fields"] = sorted(
                    set(record["conflict_fields"]) |
                    {field for event in remaining for field in event["changes"]}
                )
                record["conflict_candidates"].extend(summarize_work_record_events(remaining))
                warnings.append(f"{record_id}: unresolved or out-of-order work record edits")
        records.append(record)

    record_by_id = {record["record_id"]: record for record in records}
    for event_id, variants in duplicate_conflicts.items():
        affected = {event["record_id"] for event in variants}
        for record_id in affected:
            record = record_by_id.get(record_id)
            if record is None:
                continue
            record["conflict"] = True
            record["conflict_fields"] = sorted(set(record["conflict_fields"]) | {"event_id"})
            record["conflict_candidates"].extend(summarize_work_record_events(
                [event for event in variants if event["record_id"] == record_id]
            ))
            warnings.append(f"{record_id}: event_id {event_id} has conflicting content; needs review")

    project_map = {}
    task_map = {}
    step_map = {}
    if workspace is not None:
        project_map = {item["project_id"]: item for item in workspace.get("projects", [])}
        task_map = {item["task_id"]: item for item in workspace.get("tasks", [])}
        for task in workspace.get("tasks", []):
            for step in task.get("steps", []):
                step_map[step["step_id"]] = step

    linked_inbox: dict[str, list[str]] = defaultdict(list)
    for record in records:
        record.setdefault("occurred_at", None)
        record.setdefault("category", "other")
        record.setdefault("project_id", None)
        record.setdefault("source_ids", [])
        record.setdefault("evidence_refs", [])
        record.setdefault("action_links", [])
        record["project_name"] = None
        record["project_missing"] = False
        record["missing_action_links"] = []
        if record["project_id"]:
            project = project_map.get(record["project_id"])
            record["project_name"] = project["name"] if project and not project["conflict"] else None
            record["project_missing"] = project is None or project["conflict"]
            if record["project_missing"]:
                warnings.append(f"{record['record_id']}: referenced project has not synced or needs review")
        record["missing_source_ids"] = []
        for source_id in record["source_ids"]:
            if source_id not in {item["inbox_id"] for item in inbox}:
                record["missing_source_ids"].append(source_id)
                warnings.append(f"{record['record_id']}: source input {source_id} has not synced")
            if not record["conflict"]:
                linked_inbox[source_id].append(record["record_id"])
        for link in record["action_links"]:
            if workspace is None:
                continue
            target = task_map.get(link["target_id"]) if link["target_type"] == "task" else step_map.get(link["target_id"])
            if target is None or target.get("conflict"):
                record["missing_action_links"].append(link)
    for item in inbox:
        linked = linked_inbox.get(item["inbox_id"], [])
        item["linked_record_ids"] = sorted(set(linked))
        item["status"] = "processed" if linked else "pending"

    records.sort(key=lambda item: (
        str(item.get("occurred_at") or item.get("created_at") or ""), item["record_id"]
    ), reverse=True)
    inbox.sort(key=lambda item: (str(item.get("captured_at", "")), item["inbox_id"]), reverse=True)
    return {"inbox": inbox, "records": records, "warnings": warnings}


def validate_project_references(workspace: dict, project_id: object,
                                related_project_ids: object,
                                previous: dict | None = None) -> None:
    """Existing unsynced references may survive an edit, but cannot be newly assigned."""
    projects = {project["project_id"]: project for project in workspace["projects"]}
    previous_primary = previous.get("project_id") if previous else None
    previous_related = previous.get("related_project_ids", []) if previous else []
    if project_id is not None:
        if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
            raise ValueError("invalid primary project ID")
        project = projects.get(project_id)
        if (not project or project["conflict"]) and project_id != previous_primary:
            raise ValueError("primary project does not exist or needs conflict review")
    if (not isinstance(related_project_ids, list) or len(related_project_ids) > 20
            or any(not isinstance(item, str) or not PROJECT_ID.fullmatch(item)
                   for item in related_project_ids)
            or len(set(related_project_ids)) != len(related_project_ids)):
        raise ValueError("invalid related_project_ids")
    if project_id in related_project_ids:
        raise ValueError("primary project cannot also be a related project")
    for related_id in related_project_ids:
        project = projects.get(related_id)
        if (not project or project["conflict"]) and related_id not in previous_related:
            raise ValueError("related project does not exist or needs conflict review")


def handler_factory(data_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def allowed_hosts(self) -> set[str]:
            port = self.server.server_port
            return {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

        def local_request_allowed(self) -> bool:
            host = self.headers.get("Host", "").strip().lower()
            allowed = self.allowed_hosts()
            if host not in allowed:
                return False
            origin = self.headers.get("Origin")
            return not origin or origin in {f"http://{item}" for item in allowed if item == host}

        def respond(self, code: int, body: bytes, mime: str = "application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(body)

        def json_response(self, code: int, payload: dict):
            self.respond(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        def read_payload(self, max_body: int = MAX_BODY) -> dict:
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise TypeError("JSON required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= max_body:
                raise ValueError("invalid body length")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            return payload

        def do_GET(self):
            if not self.local_request_allowed():
                return self.json_response(403, {"error": "local requests only"})
            path = urlsplit(self.path).path
            if path == "/api/tasks":
                return self.json_response(200, read_workspace(data_dir))
            if path == "/api/work-archive":
                workspace = read_workspace(data_dir)
                return self.json_response(200, read_work_archive(data_dir, workspace))
            if path == "/api/update/status":
                return self.json_response(200, get_install_status(ROOT))
            if path == "/api/update/check":
                try:
                    return self.json_response(200, check_latest_update(ROOT))
                except UpdateError as exc:
                    return self.json_response(502, {"error": str(exc)})
            if path in {"/", "/index.html"}:
                return self.respond(200, (ROOT / "web" / "index.html").read_bytes(),
                                    "text/html; charset=utf-8")
            return self.json_response(404, {"error": "not found"})

        def do_POST(self):
            path = unquote(urlsplit(self.path).path)
            task_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/update", path)
            project_match = re.fullmatch(r"/api/projects/(PROJECT-[A-F0-9]{32})/update", path)
            step_create_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps", path)
            step_update_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/(STEP-[A-F0-9]{32})/update", path)
            step_reorder_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/reorder", path)
            work_record_update_match = re.fullmatch(
                r"/api/work-archive/records/(RECORD-[A-F0-9]{32})/update", path
            )
            creating_task = path == "/api/tasks"
            creating_project = path == "/api/projects"
            creating_work_inbox = path == "/api/work-archive/inbox"
            creating_work_record = path == "/api/work-archive/records"
            applying_update = path == "/api/update/apply"
            if not (creating_task or creating_project or creating_work_inbox or creating_work_record or
                    task_match or project_match or step_create_match or step_update_match or
                    step_reorder_match or work_record_update_match or applying_update):
                return self.json_response(404, {"error": "not found"})
            if not self.local_request_allowed():
                return self.json_response(403, {"error": "local requests only"})
            if applying_update:
                if not _update_lock.acquire(blocking=False):
                    return self.json_response(409, {"error": "update already in progress"})
                stage = None
                helper_started = False
                try:
                    payload = self.read_payload()
                    if set(payload) != {"commit"}:
                        raise ValueError("update requires the checked GitHub commit")
                    commit = payload["commit"]
                    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                        raise ValueError("invalid update commit")
                    stage, latest = prepare_update(ROOT, data_dir, commit)
                    launch_update_helper(stage, ROOT, data_dir, commit,
                                         self.server.server_port, os.getpid())
                    helper_started = True
                    try:
                        self.json_response(202, {
                            "started": True,
                            "commit": commit,
                            "version": latest["latest_version"],
                            "message": "更新包已验证，工作台正在安全重启。",
                        })
                    except OSError:
                        # The browser may disconnect after the helper has started;
                        # still stop this server so the helper can safely continue.
                        pass
                    finally:
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                except UpdateError as exc:
                    return self.json_response(502, {"error": str(exc)})
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                    return self.json_response(400, {"error": str(exc)})
                except OSError:
                    return self.json_response(500, {"error": "unable to start the update helper"})
                finally:
                    if not helper_started:
                        if stage is not None:
                            remove_stage(stage)
                        _update_lock.release()

            try:
                archive_write = creating_work_inbox or creating_work_record or bool(work_record_update_match)
                payload = self.read_payload(MAX_ARCHIVE_BODY if archive_write else MAX_BODY)
                if creating_work_inbox:
                    allowed = {"content", "occurred_at", "source", "evidence_refs", "capture_key"}
                    if set(payload) - allowed:
                        raise ValueError("unknown work inbox fields")
                    event_content = payload.get("content")
                    if not isinstance(event_content, str) or not 1 <= len(event_content.strip()) <= 12_000:
                        raise ValueError("work inbox content must be 1–12000 characters")
                    capture_key = payload.get("capture_key")
                    source = payload.get("source", "workbench")
                    occurred_at = payload.get("occurred_at") or None
                    evidence_refs = payload.get("evidence_refs", [])
                    with _write_lock:
                        archive = read_work_archive(data_dir)
                        if capture_key:
                            existing = next((item for item in archive["inbox"]
                                             if item.get("capture_key") == capture_key), None)
                            if existing:
                                same_capture = (
                                    existing["content"] == event_content and
                                    existing.get("occurred_at") == occurred_at and
                                    existing["source"] == source and
                                    existing.get("evidence_refs", []) == evidence_refs
                                )
                                if same_capture:
                                    return self.json_response(200, {
                                        "saved": True, "duplicate": True,
                                        "inbox_id": existing["inbox_id"],
                                    })
                                return self.json_response(409, {
                                    "error": "capture_key already exists with different content",
                                })
                        event = {
                            "version": 1, "event_id": str(uuid.uuid4()),
                            "inbox_id": f"INBOX-{uuid.uuid4().hex.upper()}",
                            "action": "capture", "actor": "user", "source": source,
                            "captured_at": utc_now(), "content": event_content,
                            "evidence_refs": evidence_refs,
                        }
                        if occurred_at is not None:
                            event["occurred_at"] = occurred_at
                        if capture_key:
                            event["capture_key"] = capture_key
                        append_work_inbox_event(data_dir, event)
                    return self.json_response(201, {
                        "saved": True, "inbox_id": event["inbox_id"],
                    })

                if creating_work_record:
                    allowed = {
                        "title", "summary", "occurred_at", "category", "project_id",
                        "source_ids", "evidence_refs", "action_links",
                    }
                    if set(payload) - allowed:
                        raise ValueError("unknown work record fields")
                    record_id = f"RECORD-{uuid.uuid4().hex.upper()}"
                    changes = {
                        "title": payload.get("title"),
                        "summary": payload.get("summary"),
                        "occurred_at": payload.get("occurred_at") or None,
                        "category": payload.get("category", "other"),
                        "project_id": payload.get("project_id") or None,
                        "source_ids": payload.get("source_ids", []),
                        "evidence_refs": payload.get("evidence_refs", []),
                        "action_links": payload.get("action_links", []),
                    }
                    event = {
                        "version": 1, "event_id": str(uuid.uuid4()),
                        "record_id": record_id, "action": "create", "actor": "user",
                        "timestamp": utc_now(), "base_revision": 0, "changes": changes,
                    }
                    with _write_lock:
                        append_work_record_event(data_dir, event)
                    return self.json_response(201, {
                        "saved": True, "record_id": record_id, "revision": 1,
                    })

                if work_record_update_match:
                    allowed = {
                        "revision", "title", "summary", "occurred_at", "category",
                        "project_id", "source_ids", "evidence_refs", "action_links",
                    }
                    if set(payload) - allowed or "revision" not in payload:
                        raise ValueError("work record update requires revision")
                    revision = payload["revision"]
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid work record revision")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        archive = read_work_archive(data_dir, workspace)
                        current = next((item for item in archive["records"]
                                        if item["record_id"] == work_record_update_match.group(1)), None)
                        if current is None:
                            return self.json_response(404, {"error": "work record not found"})
                        if current["conflict"] or current["revision"] != revision:
                            return self.json_response(409, {
                                "error": "work record changed or has a conflict; refresh",
                            })
                        changes = {}
                        for field in (
                            "title", "summary", "occurred_at", "category", "project_id",
                            "source_ids", "evidence_refs", "action_links",
                        ):
                            if field not in payload:
                                continue
                            value = payload[field]
                            if field in {"occurred_at", "project_id"} and value == "":
                                value = None
                            if field in {"title", "summary"} and isinstance(value, str):
                                value = value.strip()
                            if value != current.get(field, WORK_RECORD_DEFAULTS.get(field)):
                                changes[field] = value
                        if not changes:
                            return self.json_response(200, {
                                "saved": False, "record_id": current["record_id"],
                                "revision": current["revision"],
                            })
                        event = {
                            "version": 1, "event_id": str(uuid.uuid4()),
                            "record_id": current["record_id"], "action": "update",
                            "actor": "user", "timestamp": utc_now(),
                            "base_revision": revision, "changes": changes,
                        }
                        append_work_record_event(data_dir, event)
                    return self.json_response(200, {
                        "saved": True, "record_id": current["record_id"],
                        "revision": revision + 1,
                    })

                if step_create_match:
                    if set(payload) != {"title"}:
                        raise ValueError("step create accepts only title")
                    title = payload["title"]
                    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
                        raise ValueError("step title must be 1–200 characters")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == step_create_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"]:
                            return self.json_response(409, {"error": "task has an unresolved conflict; refresh"})
                        if len(task.get("steps", [])) >= MAX_STEPS_PER_TASK:
                            return self.json_response(409, {"error": "task has reached the 100-step limit"})
                        step_id = f"STEP-{uuid.uuid4().hex.upper()}"
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task["task_id"], "step_id": step_id,
                                 "action": "create", "actor": "user", "timestamp": utc_now(),
                                 "base_revision": 0, "changes": {"title": title.strip(),
                                              "position": len(task.get("steps", [])) + 1}}
                        append_step_event(data_dir, event)
                    return self.json_response(201, {"saved": True, "task_id": task["task_id"],
                                                    "step_id": step_id, "revision": 1})

                if step_update_match:
                    allowed = {"title", "status", "revision", "confirmed_done"}
                    if set(payload) - allowed or "revision" not in payload:
                        raise ValueError("step update requires revision and optional title/status")
                    if not ({"title", "status"} & set(payload)):
                        raise ValueError("step update requires a changed field")
                    revision = payload["revision"]
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid step revision")
                    if "title" in payload and (
                        not isinstance(payload["title"], str) or
                        not 1 <= len(payload["title"].strip()) <= 200
                    ):
                        raise ValueError("step title must be 1–200 characters")
                    if "status" in payload and payload["status"] not in STATUSES:
                        raise ValueError("invalid step status")
                    if payload.get("status") == "done" and payload.get("confirmed_done") is not True:
                        raise ValueError("step completion needs user confirmation")
                    if payload.get("confirmed_done") is True and payload.get("status") != "done":
                        raise ValueError("confirmed_done is only valid when completing a step")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == step_update_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"]:
                            return self.json_response(409, {"error": "task has an unresolved conflict; refresh"})
                        step = next((item for item in task.get("steps", [])
                                     if item["step_id"] == step_update_match.group(2)), None)
                        if step is None:
                            return self.json_response(404, {"error": "step not found"})
                        if step["conflict"] or step["revision"] != revision:
                            return self.json_response(409, {"error": "step changed or has a conflict; refresh"})
                        changes = {}
                        if "title" in payload and payload["title"].strip() != step["title"]:
                            changes["title"] = payload["title"].strip()
                        if "status" in payload and payload["status"] != step["status"]:
                            changes["status"] = payload["status"]
                        if not changes:
                            return self.json_response(200, {"saved": False, "step_id": step["step_id"],
                                                            "revision": step["revision"]})
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task["task_id"], "step_id": step["step_id"],
                                 "action": "update", "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "changes": changes}
                        if changes.get("status") == "done":
                            event["confirmed_done"] = True
                        append_step_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "step_id": step["step_id"],
                                                    "revision": revision + 1})

                if step_reorder_match:
                    if set(payload) != {"step_ids", "revision"}:
                        raise ValueError("step reorder requires step_ids and revision")
                    revision = payload["revision"]
                    step_ids = payload["step_ids"]
                    if type(revision) is not int or revision < 0:
                        raise ValueError("invalid step-order revision")
                    if (not isinstance(step_ids, list) or len(step_ids) > MAX_STEPS_PER_TASK
                            or any(not isinstance(item, str) or not STEP_ID.fullmatch(item) for item in step_ids)
                            or len(set(step_ids)) != len(step_ids)):
                        raise ValueError("invalid step_ids")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == step_reorder_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"]:
                            return self.json_response(409, {"error": "task has an unresolved conflict; refresh"})
                        if task["step_order_conflict"]:
                            return self.json_response(409, {"error": "step order has an unresolved conflict; refresh"})
                        if task["step_order_incomplete"]:
                            return self.json_response(
                                409,
                                {"error": "step order references steps whose creation events have not synced; wait for sync and refresh"},
                            )
                        current_ids = [item["step_id"] for item in task.get("steps", [])]
                        if len(step_ids) != len(current_ids) or set(step_ids) != set(current_ids):
                            raise ValueError("step_ids must contain every current step exactly once")
                        if revision != task["step_order_revision"]:
                            return self.json_response(409, {"error": "step order changed; refresh"})
                        if step_ids == current_ids:
                            return self.json_response(200, {"saved": False,
                                                            "revision": revision})
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task["task_id"], "action": "reorder",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "changes": {"step_ids": step_ids}}
                        append_step_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "revision": revision + 1})

                if creating_project:
                    if set(payload) != {"name"}:
                        raise ValueError("project create accepts only name")
                    name = payload["name"]
                    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
                        raise ValueError("project name must be 1–120 characters")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        if any(p["name"].casefold() == name.strip().casefold()
                               for p in workspace["projects"] if not p["conflict"]):
                            return self.json_response(409, {"error": "project name already exists"})
                        project_id = f"PROJECT-{uuid.uuid4().hex.upper()}"
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "project_id": project_id, "action": "create",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": 0, "changes": {"name": name.strip()}}
                        append_project_event(data_dir, event)
                    return self.json_response(201, {"saved": True, "project_id": project_id,
                                                    "revision": 1})

                if project_match:
                    if set(payload) != {"name", "revision"}:
                        raise ValueError("project update requires name and revision")
                    name = payload["name"]
                    revision = payload["revision"]
                    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
                        raise ValueError("project name must be 1–120 characters")
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid revision")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        current = next((p for p in workspace["projects"]
                                        if p["project_id"] == project_match.group(1)), None)
                        if not current:
                            return self.json_response(404, {"error": "project not found"})
                        if current["conflict"] or current["revision"] != revision:
                            return self.json_response(409, {"error": "project changed or has a conflict; refresh"})
                        if any(p["project_id"] != current["project_id"] and
                               p["name"].casefold() == name.strip().casefold() and not p["conflict"]
                               for p in workspace["projects"]):
                            return self.json_response(409, {"error": "project name already exists"})
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "project_id": current["project_id"], "action": "update",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "changes": {"name": name.strip()}}
                        append_project_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "project_id": project_match.group(1)})

                if creating_task:
                    if set(payload) - {"title", "project_id", "related_project_ids", *TASK_MANAGEMENT_FIELDS}:
                        raise ValueError("new task accepts title, project references and management fields only")
                    title = payload.get("title")
                    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
                        raise ValueError("title must be 1–200 characters")
                    project_id = payload.get("project_id")
                    related_ids = payload.get("related_project_ids", [])
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        validate_project_references(workspace, project_id, related_ids)
                        existing = {task["task_id"] for task in workspace["tasks"]}
                        for _ in range(5):
                            task_id = f"TASK-{uuid.uuid4().hex.upper()}"
                            if task_id not in existing:
                                break
                        else:
                            return self.json_response(409, {"error": "unable to allocate unique task ID"})
                        changes = {"title": title.strip(), "status": "todo"}
                        changes.update(normalized_task_fields(payload))
                        if "project_id" in payload:
                            changes["project_id"] = project_id
                        if "related_project_ids" in payload:
                            changes["related_project_ids"] = related_ids
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task_id, "action": "create",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": 0, "changes": changes}
                        validate_event(event)
                        append_event(data_dir, event)
                    return self.json_response(201, {"saved": True, "task_id": task_id, "revision": 1})

                if task_match:
                    allowed = {"title", "status", "revision", "project_id",
                               "related_project_ids", "confirmed_done", *TASK_MANAGEMENT_FIELDS}
                    if set(payload) - allowed:
                        raise ValueError("unknown task update fields")
                    title = payload.get("title")
                    status = payload.get("status")
                    revision = payload.get("revision")
                    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
                        raise ValueError("title must be 1–200 characters")
                    if status not in STATUSES:
                        raise ValueError("invalid status")
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid revision")
                    if status == "done" and payload.get("confirmed_done") is not True:
                        raise ValueError("completion needs user confirmation")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        tasks = {task["task_id"]: task for task in workspace["tasks"]}
                        current = tasks.get(task_match.group(1))
                        if not current:
                            return self.json_response(404, {"error": "task not found"})
                        if current["conflict"] or current["revision"] != revision:
                            return self.json_response(409, {"error": "task changed or has a conflict; refresh"})
                        changes = {"title": title.strip(), "status": status}
                        for field, value in normalized_task_fields(payload).items():
                            if value != current.get(field, TASK_DEFAULTS[field]):
                                changes[field] = value
                        if "project_id" in payload or "related_project_ids" in payload:
                            project_id = payload.get("project_id", current.get("project_id"))
                            related_ids = payload.get("related_project_ids", current.get("related_project_ids", []))
                            validate_project_references(workspace, project_id, related_ids, current)
                            if "project_id" in payload and project_id != current.get("project_id"):
                                changes["project_id"] = project_id
                            if ("related_project_ids" in payload and
                                    related_ids != current.get("related_project_ids", [])):
                                changes["related_project_ids"] = related_ids
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": current["task_id"], "action": "update",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "changes": changes}
                        if status == "done":
                            event["confirmed_done"] = True
                        validate_event(event)
                        append_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "task_id": task_match.group(1)})
            except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                code = 415 if str(exc) == "JSON required" else 400
                return self.json_response(code, {"error": str(exc)})
            except OSError:
                return self.json_response(500, {"error": "unable to save event"})

        def log_message(self, format_string, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Local AIWorkSpace task viewer/editor")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(args.data_dir))
    print(f"AIWorkSpace: http://127.0.0.1:{server.server_port}/")
    print("Local-only demo. No AI credentials or public network endpoint.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
