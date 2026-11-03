"""Small local AIWorkSpace server; no external dependencies or credentials.

Put this file next to ``web/index.html``. Set ``--data-dir`` to a folder that
Google Drive for desktop synchronizes, or omit it for isolated demo data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from updater import (UpdateError, check_latest_update, get_install_status,
                     launch_update_helper, prepare_update, remove_stage)


ROOT = Path(__file__).resolve().parent
TASK_ID = re.compile(r"^TASK-[A-Za-z0-9-]{1,50}$")
PROJECT_ID = re.compile(r"^PROJECT-[A-F0-9]{32}$")
STEP_ID = re.compile(r"^STEP-[A-F0-9]{32}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9-]{8,80}$")
STATUSES = {"todo", "doing", "blocked", "done"}
TASK_LIFECYCLE_ACTIONS = {"trash", "restore", "purge"}
MAX_DOCUMENT_LINKS = 20
PRIORITIES = {"low", "normal", "high", "urgent"}
DATE_FIELDS = ("due_date", "planned_date", "follow_up_date")
TASK_MANAGEMENT_FIELDS = ("owner", "priority", *DATE_FIELDS)
TASK_DEFAULTS = {"owner": None, "priority": "normal",
                 "due_date": None, "planned_date": None, "follow_up_date": None}
MAX_BODY = 16_384
MAX_STEPS_PER_TASK = 100
_write_lock = threading.Lock()
_update_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def display_task_id(task_id: str, created_at: str = "") -> str:
    """Derive a short, stable user-facing identifier without changing event IDs."""
    day = "000000"
    if isinstance(created_at, str):
        matched = re.match(r"^(\d{4})-(\d{2})-(\d{2})", created_at)
        if matched:
            try:
                date.fromisoformat("-".join(matched.groups()))
                day = "".join(matched.groups())[2:]
            except ValueError:
                pass
    matched_uuid = re.fullmatch(r"TASK-([0-9a-fA-F]{32})", task_id)
    suffix = (matched_uuid.group(1)[:12].upper() if matched_uuid else
              hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12].upper())
    return f"T-{day}-{suffix}"



def validate_document_links(links: object) -> list[dict]:
    """Only save Google HTTPS references. Actual AI reading requires Drive access."""
    if not isinstance(links, list) or len(links) > MAX_DOCUMENT_LINKS:
        raise ValueError("document_links must be a list of up to 20 items")
    seen = set()
    results = []
    for item in links:
        if not isinstance(item, dict) or set(item) != {"title", "url"}:
            raise ValueError("document link requires title and url")
        title, url = item["title"], item["url"]
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("document title length must be 1-120")
        if not isinstance(url, str) or not 1 <= len(url) <= 2048:
            raise ValueError("invalid document URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in
                {"drive.google.com", "docs.google.com"} or
                parsed.username or parsed.password or parsed.port or parsed.fragment or
                any(ord(char) < 32 for char in url)):
            raise ValueError("only Google Drive HTTPS links are supported")
        if parsed.hostname == "drive.google.com":
            valid = (re.fullmatch(r"/file/d/[A-Za-z0-9_-]+(/view)?/?", parsed.path) or
                     re.fullmatch(r"/drive/(u/[0-9]+/)?folders/[A-Za-z0-9_-]+/?", parsed.path) or
                     (parsed.path == "/open" and
                      re.fullmatch(r"[A-Za-z0-9_-]+", parse_qs(parsed.query).get("id", [""])[0])))
        else:
            valid = re.fullmatch(
                r"/(document|spreadsheets|presentation)/d/[A-Za-z0-9_-]+(/.*)?",
                parsed.path)
        if not valid:
            raise ValueError("unsupported Google Drive link format")
        if url in seen:
            raise ValueError("duplicate document link")
        seen.add(url)
        results.append({"title": title.strip(), "url": url})
    return results


def resolve_step_status(task: dict) -> None:
    """No synthetic event: derive aggregate status from reliably synced steps."""
    task["manual_status"] = task["status"]
    task["status_source"] = "task"
    task["step_completion_pending"] = False
    steps = task.get("steps", [])
    if (not steps or task.get("conflict") or task.get("step_order_conflict")
            or task.get("step_order_incomplete")
            or any(item.get("conflict") for item in steps)):
        return
    statuses = {item["status"] for item in steps}
    if statuses == {"done"} and task["status"] != "done":
        task["step_completion_pending"] = True
    if task["status"] == "done":
        task["status_source"] = "user_confirmed"
        return
    task["status"] = ("blocked" if "blocked" in statuses else
                      "doing" if "done" in statuses or "doing" in statuses else "todo")
    task["status_source"] = "steps"


def validate_event(value: object) -> dict:
    """Validate both remote ChatGPT files and locally generated events."""
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("version must be 1")
    if not isinstance(value.get("event_id"), str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid event_id")
    if not isinstance(value.get("task_id"), str) or not TASK_ID.fullmatch(value["task_id"]):
        raise ValueError("invalid task_id")
    if value.get("action") not in {"create", "update", *TASK_LIFECYCLE_ACTIONS}:
        raise ValueError("invalid action")
    if value.get("actor") not in {"chatgpt", "user"}:
        raise ValueError("invalid actor")
    revision = value.get("base_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid base_revision")
    changes = value.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("changes must be a nonempty object")
    if value["action"] in TASK_LIFECYCLE_ACTIONS:
        if value["actor"] != "user" or revision < 1:
            raise ValueError("task lifecycle must be a user action on existing task")
        expected = {"trash": "trashed_at", "restore": "trashed_at",
                    "purge": "purged_at"}[value["action"]]
        if set(changes) != {expected}:
            raise ValueError("unexpected lifecycle fields")
        stamp = changes[expected]
        if value["action"] == "restore":
            if stamp is not None:
                raise ValueError("restore must clear trashed_at")
        elif not isinstance(stamp, str):
            raise ValueError("lifecycle timestamp required")
        else:
            try:
                if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError as exc:
                raise ValueError("invalid lifecycle timestamp") from exc
        return value
    if set(changes) - {"title", "status", "project_id", "related_project_ids",
                       "document_links", *TASK_MANAGEMENT_FIELDS}:
        raise ValueError("unknown fields")
    if "document_links" in changes:
        validate_document_links(changes["document_links"])
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
    if value.get("action") not in {"create", "update", "reorder", "delete"}:
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
                     "timestamp", "base_revision", "changes", "confirmed_done",
                     "confirmed_delete"}:
        raise ValueError("unknown step event fields")
    if not isinstance(value.get("step_id"), str) or not STEP_ID.fullmatch(value["step_id"]):
        raise ValueError("invalid step_id")
    if value["action"] == "delete":
        if (value["actor"] != "user" or revision < 1 or
                value.get("confirmed_delete") is not True or
                set(changes) != {"deleted_at"}):
            raise ValueError("step deletion requires explicit user confirmation and revision")
        stamp = changes["deleted_at"]
        if not isinstance(stamp, str):
            raise ValueError("step deletion timestamp required")
        try:
            if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
                raise ValueError("timezone required")
        except ValueError as exc:
            raise ValueError("invalid step deletion timestamp") from exc
        if "confirmed_done" in value:
            raise ValueError("unexpected step completion confirmation")
        return value
    if "confirmed_delete" in value:
        raise ValueError("unexpected step deletion confirmation")
    if set(changes) - {"title", "status", "position", "document_links"}:
        raise ValueError("unknown step fields")
    if "document_links" in changes:
        validate_document_links(changes["document_links"])
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
                    "document_links": [], "deleted_at": None,
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
                "document_links": [], "deleted_at": None,
            }
            if len(task_ids) != 1:
                step["conflict"] = True
                step["conflict_fields"] = ["task_id"]
                step["conflict_candidates"] = summarize_conflict_events(events)
                warnings.append(f"{step_id}: events reference different parent tasks")
            updates: dict[int, list[dict]] = defaultdict(list)
            for event in events:
                if event["action"] in {"update", "delete"}:
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
                selected = candidates[0]
                # A delete tombstone cannot be undone by a late edit.
                if step.get("deleted_at"):
                    step["conflict"] = True
                    step["conflict_fields"] = sorted(set(step["conflict_fields"]) | {"deleted_at"})
                    step["conflict_candidates"].extend(summarize_conflict_events(candidates))
                    warnings.append(f"{step_id}: events after step deletion need review")
                    break
                step.update(selected["changes"])
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
        # Old reorder events can mention an already deleted step. This is not a
        # sync gap: only missing creation events cause order_incomplete.
        live_steps = [step for step in ordered if not step.get("deleted_at")]
        for index, step in enumerate(live_steps, start=1):
            step["position"] = index
        task["steps"] = live_steps
        task["step_order_revision"] = order_revision
        task["step_order_conflict"] = order_conflict
        task["step_order_incomplete"] = bool(missing_order_ids)
        task["step_order_missing_ids"] = missing_order_ids
        task["step_order_candidates"] = order_candidates
        resolve_step_status(task)


def read_workspace(data_dir: Path, include_trashed: bool = False) -> dict:
    """Reduce independent event files; never silently choose a concurrent edit."""
    event_dir = data_dir / "events"
    created: dict[str, list[dict]] = defaultdict(list)
    updated: dict[str, list[dict]] = defaultdict(list)
    purged_ids: set[str] = set()
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
            if event["action"] == "purge":
                purged_ids.add(event["task_id"])
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            warnings.append(f"{path.name}: {exc}")

    tasks: list[dict] = []
    for task_id in sorted(set(created) | set(updated)):
        if task_id in purged_ids:
            continue  # Irrevocable marker prevents resurrection on delayed sync.
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
                "trashed_at": None,
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

    # User-facing identifiers are derived at read time. Historical append-only
    # events and API/step/project foreign keys retain the original TASK UUID.
    used_display_ids: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        creation = created.get(task["task_id"], [])
        if len(creation) != 1:
            task["display_id"] = task["task_id"]
            continue
        task["created_at"] = creation[0].get("timestamp", "")
        task["display_id"] = display_task_id(task["task_id"], task["created_at"])
        used_display_ids[task["display_id"]].append(task)
    for short_id, duplicates in used_display_ids.items():
        if len(duplicates) > 1:
            for task in duplicates:
                task["display_id"] = task["task_id"]
            warnings.append(f"display identifier collision: {short_id}; using full IDs")

    project_map = {project["project_id"]: project for project in project_state["projects"]}
    for task in tasks:
        for field, default in TASK_DEFAULTS.items():
            task.setdefault(field, default)
        task.setdefault("project_id", None)
        task.setdefault("related_project_ids", [])
        task.setdefault("document_links", [])
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
    if not include_trashed:
        tasks = [task for task in tasks if not task.get("trashed_at")]
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




def validate_setting_event(value: object) -> dict:
    """Validate the shared retention settings event schema for review discovery."""
    if (not isinstance(value, dict) or value.get("version") != 1 or
            not isinstance(value.get("event_id"), str) or
            not EVENT_ID.fullmatch(value["event_id"]) or
            value.get("key") != "trash_retention_days" or
            type(value.get("days")) is not int or value["days"] not in {0, 7, 30, 90}):
        raise ValueError("invalid shared trash retention setting")
    stamp = value.get("timestamp")
    if not isinstance(stamp, str):
        raise ValueError("settings timestamp required")
    try:
        if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise ValueError("invalid settings timestamp") from exc
    return value


REVIEW_ID = re.compile(r"^ANOM-[A-F0-9]{32}$")
REVIEW_HASH = re.compile(r"^[a-f0-9]{64}$")
REVIEW_FOLDERS = {"events", "project_events", "step_events", "settings_events"}
REVIEW_ACTIONS = {"authorize", "applied", "dismissed", "stale", "failed"}


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _review_snapshot(anomaly: dict) -> dict:
    return {key: anomaly.get(key) for key in
            ("category", "title", "reason", "event_id", "task_id", "step_id", "action")}


def validate_review_event(value: object) -> dict:
    """Validate an append-only human review/authorization/result record."""
    required = {"version", "event_id", "anomaly_id", "action", "actor", "timestamp",
                "base_revision", "source", "snapshot", "changes"}
    if not isinstance(value, dict) or set(value) != required or value.get("version") != 1:
        raise ValueError("invalid review event shape")
    if not isinstance(value["event_id"], str) or not EVENT_ID.fullmatch(value["event_id"]):
        raise ValueError("invalid review event_id")
    if not isinstance(value["anomaly_id"], str) or not REVIEW_ID.fullmatch(value["anomaly_id"]):
        raise ValueError("invalid anomaly_id")
    if value["action"] not in REVIEW_ACTIONS or value["actor"] != "user":
        raise ValueError("review action must be an explicit user decision")
    revision = value["base_revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid review revision")
    stamp = value["timestamp"]
    if not isinstance(stamp, str):
        raise ValueError("review timestamp required")
    try:
        if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise ValueError("invalid review timestamp") from exc
    source = value["source"]
    if (not isinstance(source, dict) or set(source) != {"folder", "filename", "sha256"}
            or source["folder"] not in REVIEW_FOLDERS | {"workspace"}
            or not isinstance(source["filename"], str)
            or not isinstance(source["sha256"], str)
            or not REVIEW_HASH.fullmatch(source["sha256"])):
        raise ValueError("invalid review source")
    if source["folder"] == "workspace":
        if source["filename"]:
            raise ValueError("workspace review source cannot name a file")
    elif (not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}\.json", source["filename"])
          or source["filename"] in {".", ".."}):
        raise ValueError("invalid review source filename")
    snapshot = value["snapshot"]
    snapshot_fields = {"category", "title", "reason", "event_id", "task_id", "step_id", "action"}
    if not isinstance(snapshot, dict) or set(snapshot) != snapshot_fields:
        raise ValueError("invalid review snapshot")
    for field in ("category", "title", "reason"):
        if not isinstance(snapshot[field], str) or len(snapshot[field]) > 2000:
            raise ValueError("invalid review snapshot text")
    for field in ("event_id", "task_id", "step_id", "action"):
        if snapshot[field] is not None and (
            not isinstance(snapshot[field], str) or len(snapshot[field]) > 200
        ):
            raise ValueError("invalid review snapshot reference")
    changes = value["changes"]
    if not isinstance(changes, dict):
        raise ValueError("review changes must be an object")
    if value["action"] == "authorize":
        if set(changes) != {"approved_event", "proposal_sha256", "note"}:
            raise ValueError("authorization requires approved event and proposal hash")
        if (not isinstance(changes["proposal_sha256"], str)
                or not REVIEW_HASH.fullmatch(changes["proposal_sha256"])
                or not isinstance(changes["note"], str) or len(changes["note"]) > 500):
            raise ValueError("invalid authorization details")
        approved = changes["approved_event"]
        if source["folder"] == "events":
            validate_event(approved)
        elif source["folder"] == "step_events":
            validate_step_event(approved)
        elif source["folder"] == "project_events":
            validate_project_event(approved)
        elif source["folder"] == "settings_events":
            validate_setting_event(approved)
        else:
            raise ValueError("workspace warnings cannot authorize event writes")
        if approved.get("actor") != "user":
            raise ValueError("approved event must be a user action")
    elif value["action"] == "applied":
        if set(changes) != {"target_event_id", "target_folder", "target_filename",
                            "target_sha256", "verified_revision"}:
            raise ValueError("invalid applied receipt")
        if (not isinstance(changes["target_event_id"], str)
                or not EVENT_ID.fullmatch(changes["target_event_id"])
                or changes["target_folder"] not in REVIEW_FOLDERS
                or changes["target_filename"] != f"evt_{changes['target_event_id']}.json"
                or not isinstance(changes["target_sha256"], str)
                or not REVIEW_HASH.fullmatch(changes["target_sha256"])
                or type(changes["verified_revision"]) is not int
                or changes["verified_revision"] < 1):
            raise ValueError("invalid applied receipt fields")
    elif value["action"] == "dismissed":
        if set(changes) != {"note"} or not isinstance(changes["note"], str) or not 1 <= len(changes["note"].strip()) <= 500:
            raise ValueError("a 1–500 character review reason is required")
    else:
        if set(changes) != {"reason"} or not isinstance(changes["reason"], str) or not 1 <= len(changes["reason"].strip()) <= 500:
            raise ValueError("a 1–500 character result reason is required")
    return value


def append_review_event(data_dir: Path, event: dict) -> Path:
    validate_review_event(event)
    return _append_json_event(data_dir, event, "review_events")


def read_review_states(data_dir: Path) -> tuple[dict, list[str]]:
    """Reduce immutable review records; same-revision decisions become conflicts."""
    directory = data_dir / "review_events"
    groups: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, dict] = {}
    duplicate_ids: set[str] = set()
    warnings: list[str] = []
    if not directory.is_dir() or directory.is_symlink():
        return {}, warnings
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BODY * 2:
                raise ValueError("review event file too large")
            event = validate_review_event(json.loads(path.read_text(encoding="utf-8-sig")))
            previous = seen.get(event["event_id"])
            if previous is not None:
                if previous == event:
                    continue
                duplicate_ids.add(event["anomaly_id"])
                warnings.append(f"{path.name}: duplicate review event_id with conflicting content")
                continue
            seen[event["event_id"]] = event
            groups[event["anomaly_id"]].append(event)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            warnings.append(f"{path.name}: review record needs inspection ({exc})")
    states = {}
    for anomaly_id, events in groups.items():
        events.sort(key=lambda item: (item["base_revision"], item["timestamp"], item["event_id"]))
        expected = 0
        latest = None
        timeline = []
        conflict = anomaly_id in duplicate_ids
        source = None
        for revision, candidates_iter in __import__("itertools").groupby(
                events, key=lambda item: item["base_revision"]):
            candidates = list(candidates_iter)
            if revision != expected or len(candidates) != 1:
                conflict = True
                break
            candidate = candidates[0]
            if source is not None and candidate["source"] != source:
                conflict = True
                break
            source = candidate["source"]
            latest = candidate
            timeline.append(candidate)
            expected += 1
        status = "conflict" if conflict else (
            {"authorize": "authorized", "applied": "applied", "dismissed": "dismissed",
             "stale": "stale", "failed": "failed"}.get(latest["action"], "pending")
            if latest else "pending")
        states[anomaly_id] = {
            "status": status, "revision": expected, "latest": latest,
            "timeline": timeline, "snapshot": latest["snapshot"] if latest else {},
            "source": source,
        }
    return states, warnings


def _classify_invalid_event(folder: str, event: object, reason: str) -> tuple[str, str]:
    if folder == "events" and isinstance(event, dict) and event.get("action") in TASK_LIFECYCLE_ACTIONS:
        return "task_lifecycle_requires_user", "任务生命周期事件缺少有效的用户操作授权或版本"
    if (folder == "step_events" and isinstance(event, dict)
            and event.get("action") == "update" and "cannot set position" in reason):
        return "step_update_position", "执行步骤更新包含不允许的 position 字段"
    if "explicit user confirmation" in reason or "completion needs" in reason:
        return "completion_confirmation_missing", "完成状态缺少用户明确确认"
    if any(token in reason.lower() for token in
           ("expecting", "delimiter", "property name", "extra data", "utf-8", "encoding")):
        return "malformed_event", "事件文件格式或编码异常"
    return "invalid_event", "事件未通过数据结构与业务规则校验"


def scan_invalid_event_files(data_dir: Path) -> tuple[list[dict], list[str]]:
    """Discover invalid immutable source files without changing or quarantining them."""
    validators = {"events": validate_event, "project_events": validate_project_event,
                  "step_events": validate_step_event, "settings_events": validate_setting_event}
    anomalies: list[dict] = []
    warnings: list[str] = []
    for folder, validator in validators.items():
        directory = data_dir / folder
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            event = None
            try:
                raw = path.read_bytes()
                source_hash = hashlib.sha256(raw).hexdigest()
                if len(raw) > MAX_BODY:
                    event, reason = None, "file too large"
                else:
                    try:
                        event = json.loads(raw.decode("utf-8-sig"))
                        validator(event)
                        continue
                    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                        reason = str(exc)
            except OSError as exc:
                warnings.append(f"{path.name}: unable to inspect source ({exc})")
                continue
            category, title = _classify_invalid_event(folder, event, reason)
            anomaly_id = "ANOM-" + hashlib.sha256(
                f"{folder}/{path.name}:{source_hash}".encode("utf-8")
            ).hexdigest()[:32].upper()
            raw_excerpt = None
            if not isinstance(event, dict):
                raw_excerpt = raw[:2400].decode("utf-8", errors="replace")
            anomalies.append({
                "anomaly_id": anomaly_id, "category": category, "title": title,
                "reason": reason, "source": {"folder": folder, "filename": path.name,
                                             "sha256": source_hash},
                "source_present": True, "source_event": event if isinstance(event, dict) else None,
                "raw_excerpt": raw_excerpt,
                "event_id": event.get("event_id") if isinstance(event, dict) else None,
                "task_id": event.get("task_id") if isinstance(event, dict) else None,
                "step_id": event.get("step_id") if isinstance(event, dict) else None,
                "action": event.get("action") if isinstance(event, dict) else None,
            })
    return anomalies, warnings


def _workspace_warning_anomalies(workspace: dict, known_filenames: set[str]) -> list[dict]:
    results = []
    ignored = ("identical event; ignored", "identical; ignored",
               "display identifier collision")
    for warning in workspace.get("warnings", []):
        if any(token in warning for token in ignored):
            continue
        if any(warning.startswith(filename + ":") for filename in known_filenames):
            continue
        category = ("sync_pending" if any(token in warning for token in
                     ("waiting for", "not synced", "has not synced", "尚未同步"))
                    else "semantic_conflict")
        source_hash = hashlib.sha256(warning.encode("utf-8")).hexdigest()
        anomaly_id = "ANOM-" + hashlib.sha256(
            ("workspace:" + source_hash).encode("utf-8")
        ).hexdigest()[:32].upper()
        results.append({
            "anomaly_id": anomaly_id, "category": category,
            "title": "数据正在等待同步" if category == "sync_pending" else "数据引用或版本存在冲突",
            "reason": warning,
            "source": {"folder": "workspace", "filename": "", "sha256": source_hash},
            "source_present": True, "source_event": None, "raw_excerpt": None,
            "event_id": None, "task_id": None, "step_id": None, "action": None,
        })
    return results


def _build_review_proposal(data_dir: Path, anomaly: dict, workspace: dict) -> dict | None:
    """Build a preview only; it never writes. Unsupported/destructive fixes stay manual."""
    source_event = anomaly.get("source_event")
    folder = anomaly["source"]["folder"]
    if not isinstance(source_event, dict):
        return None
    task_id = source_event.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
        return None
    task = next((item for item in workspace.get("tasks", [])
                 if item.get("task_id") == task_id), None)
    if not task or task.get("conflict") or task.get("trashed_at"):
        return None
    event_fields = None
    requires_completion_confirmation = False
    explanation = ""
    action = source_event.get("action")
    changes = source_event.get("changes")
    if not isinstance(changes, dict):
        return None

    if folder == "events" and anomaly["category"] == "task_lifecycle_requires_user":
        # Purge remains a separate destructive workflow; never repair it from this queue.
        if action not in {"trash", "restore"} or task.get("revision", 0) < 1:
            return None
        if action == "trash":
            if task.get("trashed_at"):
                return None
            stamp = changes.get("trashed_at") or source_event.get("timestamp")
            if not isinstance(stamp, str):
                return None
            try:
                if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
                    return None
            except ValueError:
                return None
            next_changes = {"trashed_at": stamp}
        else:
            if not task.get("trashed_at") or changes.get("trashed_at", None) is not None:
                return None
            next_changes = {"trashed_at": None}
        event_fields = {"version": 1, "task_id": task_id, "action": action,
                        "actor": "user", "base_revision": task["revision"],
                        "changes": next_changes}
        explanation = "以当前任务修订号重新生成合法的用户生命周期事件；原始异常事件保持不变。"
    elif folder == "step_events" and anomaly["category"] in {
            "step_update_position", "completion_confirmation_missing"}:
        step_id = source_event.get("step_id")
        if not isinstance(step_id, str) or not STEP_ID.fullmatch(step_id):
            return None
        step = next((item for item in task.get("steps", [])
                     if item.get("step_id") == step_id), None)
        if not step or step.get("conflict") or step.get("revision", 0) < 1:
            return None
        if action != "update":
            return None
        allowed = {"title", "status"}
        if set(changes) - (allowed | ({"position"} if anomaly["category"] == "step_update_position" else set())):
            return None
        next_changes = {key: value for key, value in changes.items() if key in allowed}
        if not next_changes:
            return None
        if next_changes.get("status") == "done":
            requires_completion_confirmation = True
        event_fields = {"version": 1, "task_id": task_id, "step_id": step_id,
                        "action": "update", "actor": "user",
                        "base_revision": step["revision"], "changes": next_changes}
        if requires_completion_confirmation:
            event_fields["confirmed_done"] = True
        explanation = (
            "按当前步骤修订号重新生成合法更新；舍弃原事件中非法的 position 字段。"
            if anomaly["category"] == "step_update_position" else
            "由用户明确确认该步骤完成后，重新生成带 confirmed_done 的合法事件。"
        )
    elif folder == "events" and anomaly["category"] == "completion_confirmation_missing":
        if action != "update" or changes.get("status") != "done" or task["revision"] < 1:
            return None
        allowed = {"title", "status", "project_id", "related_project_ids",
                   "document_links", *TASK_MANAGEMENT_FIELDS}
        if set(changes) - allowed:
            return None
        next_changes = dict(changes)
        event_fields = {"version": 1, "task_id": task_id, "action": "update",
                        "actor": "user", "base_revision": task["revision"],
                        "changes": next_changes, "confirmed_done": True}
        requires_completion_confirmation = True
        explanation = "用户明确确认任务完成后，按当前任务修订号重新生成合法事件。"
    else:
        return None

    event_fields["event_id"] = "repair-" + _canonical_hash({
        "anomaly_id": anomaly["anomaly_id"], "folder": folder,
        "event": event_fields
    })[:32]
    validator = {"events": validate_event, "step_events": validate_step_event}.get(folder)
    if not validator:
        return None
    try:
        validator(event_fields)
    except (ValueError, TypeError):
        return None
    proposal_hash = _canonical_hash({"folder": folder, "event": event_fields})
    target = {"task_id": task_id}
    if "step_id" in event_fields:
        target["step_id"] = event_fields["step_id"]
        target["step_title"] = next((item["title"] for item in task["steps"]
                                     if item["step_id"] == event_fields["step_id"]), "")
    else:
        target["task_title"] = task.get("title", "")
    return {
        "target_folder": folder, "target": target, "event": event_fields,
        "proposal_sha256": proposal_hash,
        "requires_completion_confirmation": requires_completion_confirmation,
        "explanation": explanation,
    }


def list_data_reviews(data_dir: Path, workspace: dict | None = None) -> dict:
    """Return all current anomalies plus immutable review history and summary."""
    workspace = workspace if workspace is not None else read_workspace(data_dir, include_trashed=True)
    anomalies, scan_warnings = scan_invalid_event_files(data_dir)
    _, policy_warnings = read_trash_retention(data_dir)
    workspace_with_policy = {
        **workspace, "warnings": list(workspace.get("warnings", [])) + policy_warnings
    }
    known_filenames = {item["source"]["filename"] for item in anomalies}
    anomalies.extend(_workspace_warning_anomalies(workspace_with_policy, known_filenames))
    states, review_warnings = read_review_states(data_dir)
    current_ids = set()
    items = []
    for anomaly in anomalies:
        anomaly_id = anomaly["anomaly_id"]
        current_ids.add(anomaly_id)
        state = states.get(anomaly_id)
        status = state["status"] if state else "pending"
        proposal = _build_review_proposal(data_dir, anomaly, workspace)
        latest = state["latest"] if state else None
        if state and state["status"] == "authorized":
            approved = latest["changes"]["approved_event"]
            if (not anomaly["source_present"] or
                    _canonical_hash({"folder": anomaly["source"]["folder"],
                                     "event": {key: value for key, value in approved.items()
                                               if key != "timestamp"}}) !=
                    latest["changes"]["proposal_sha256"]):
                # The next action must re-check and re-authorize; do not auto-write.
                status = "stale"
            elif proposal is None or proposal["proposal_sha256"] != latest["changes"]["proposal_sha256"]:
                status = "stale"
        item = dict(anomaly)
        item.update({
            "status": status, "review_revision": state["revision"] if state else 0,
            "timeline": [{
                "action": event["action"], "timestamp": event["timestamp"],
                "note": event["changes"].get("note", event["changes"].get("reason", "")),
                "event_id": event["event_id"],
            } for event in (state["timeline"] if state else [])],
            "authorization_event_id": latest["event_id"] if latest and latest["action"] == "authorize" else None,
            "proposal": proposal,
            "can_authorize": bool(proposal and status in {"pending", "failed", "stale"}
                                  and anomaly["source_present"] and not (state and state["status"] == "conflict")),
            "can_apply": bool(status == "authorized" and proposal and anomaly["source_present"]
                              and latest and latest["action"] == "authorize"),
            "can_dismiss": bool(status in {"pending", "authorized", "failed", "stale"}
                                and anomaly["source_present"] and not (state and state["status"] == "conflict")),
        })
        items.append(item)
    # Keep an audit trail visible even if a synced source file later disappears.
    for anomaly_id, state in states.items():
        if anomaly_id in current_ids:
            continue
        latest = state["latest"]
        snapshot = state["snapshot"] or {}
        status = state["status"]
        if status == "authorized":
            status = "stale"
        items.append({
            "anomaly_id": anomaly_id, "category": snapshot.get("category", "historical"),
            "title": snapshot.get("title", "历史核查记录"),
            "reason": snapshot.get("reason", "原始异常文件已不存在；保留核查历史。"),
            "source": state["source"], "source_present": False,
            "source_event": None, "raw_excerpt": None,
            "event_id": snapshot.get("event_id"), "task_id": snapshot.get("task_id"),
            "step_id": snapshot.get("step_id"), "action": snapshot.get("action"),
            "status": status, "review_revision": state["revision"],
            "timeline": [{
                "action": event["action"], "timestamp": event["timestamp"],
                "note": event["changes"].get("note", event["changes"].get("reason", "")),
                "event_id": event["event_id"],
            } for event in state["timeline"]],
            "authorization_event_id": None, "proposal": None,
            "can_authorize": False, "can_apply": False, "can_dismiss": False,
        })
    order = {"pending": 0, "authorized": 1, "failed": 2, "stale": 3,
             "conflict": 4, "dismissed": 5, "applied": 6}
    items.sort(key=lambda item: (order.get(item["status"], 9), item["source"]["folder"],
                                 item["source"]["filename"], item["anomaly_id"]))
    counts = {key: sum(item["status"] == key for item in items)
              for key in ("pending", "authorized", "applied", "dismissed", "stale", "failed", "conflict")}
    counts["total"] = len(items)
    counts["open_count"] = (counts["pending"] + counts["authorized"] + counts["stale"]
                            + counts["failed"] + counts["conflict"])
    counts["reviewable_count"] = sum(
        bool(item["can_authorize"] or item["can_dismiss"]) for item in items
    )
    return {"items": items, "summary": counts,
            "warnings": scan_warnings + review_warnings}


def _load_current_anomaly(data_dir: Path, anomaly: dict) -> tuple[dict | None, str | None]:
    source = anomaly["source"]
    if source["folder"] == "workspace":
        workspace = read_workspace(data_dir, include_trashed=True)
        _, policy_warnings = read_trash_retention(data_dir)
        workspace = {**workspace, "warnings": list(workspace.get("warnings", [])) + policy_warnings}
        current = next((item for item in _workspace_warning_anomalies(workspace, set())
                       if item["anomaly_id"] == anomaly["anomaly_id"]), None)
        return current, None if current else "workspace warning has cleared"
    if source["folder"] not in REVIEW_FOLDERS:
        return None, "unsupported source folder"
    filename = source["filename"]
    if (not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}\.json", filename)
            or filename in {".", ".."}):
        return None, "invalid source filename"
    path = data_dir / source["folder"] / filename
    if path.is_symlink() or not path.is_file():
        return None, "original source file is missing or unsafe"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"unable to read original source: {exc}"
    digest = hashlib.sha256(raw).hexdigest()
    if digest != source["sha256"]:
        return None, "original source changed after review"
    if len(raw) > MAX_BODY:
        reason = "file too large"
        event = None
    else:
        try:
            event = json.loads(raw.decode("utf-8-sig"))
            validator = {"events": validate_event, "project_events": validate_project_event,
                         "step_events": validate_step_event,
                         "settings_events": validate_setting_event}[source["folder"]]
            validator(event)
            return None, "source event is now valid; review is stale"
        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            reason = str(exc)
    category, title = _classify_invalid_event(source["folder"], event, reason)
    current = {
        "anomaly_id": anomaly["anomaly_id"], "category": category, "title": title,
        "reason": reason, "source": source, "source_present": True,
        "source_event": event if isinstance(event, dict) else None,
        "raw_excerpt": raw[:2400].decode("utf-8", errors="replace") if event is None else None,
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
        "task_id": event.get("task_id") if isinstance(event, dict) else None,
        "step_id": event.get("step_id") if isinstance(event, dict) else None,
        "action": event.get("action") if isinstance(event, dict) else None,
    }
    return current, None


def _new_review_record(anomaly: dict, action: str, revision: int, changes: dict) -> dict:
    return {
        "version": 1, "event_id": str(uuid.uuid4()),
        "anomaly_id": anomaly["anomaly_id"], "action": action, "actor": "user",
        "timestamp": utc_now(), "base_revision": revision,
        "source": dict(anomaly["source"]), "snapshot": _review_snapshot(anomaly),
        "changes": changes,
    }


def _append_review_transition(data_dir: Path, anomaly: dict, state: dict | None,
                              action: str, changes: dict) -> dict:
    if state and state["status"] == "conflict":
        raise ValueError("review history has a conflict; stop and inspect the review records")
    event = _new_review_record(anomaly, action, state["revision"] if state else 0, changes)
    append_review_event(data_dir, event)
    return event


def perform_review_action(data_dir: Path, anomaly_id: str, action: str,
                          payload: dict) -> tuple[int, dict]:
    """Separate review, explicit authorization, validated append, and receipt."""
    if not REVIEW_ID.fullmatch(anomaly_id):
        return 400, {"error": "invalid anomaly_id"}
    workspace = read_workspace(data_dir, include_trashed=True)
    register = list_data_reviews(data_dir, workspace)
    item = next((entry for entry in register["items"] if entry["anomaly_id"] == anomaly_id), None)
    if item is None:
        return 404, {"error": "anomaly not found"}
    states, state_warnings = read_review_states(data_dir)
    state = states.get(anomaly_id)
    if state and state["status"] == "conflict":
        return 409, {"error": "review history conflict; no write is allowed"}
    if item["source"]["sha256"] != payload.get("source_sha256"):
        return 409, {"error": "source hash changed; refresh and review again"}

    if action == "dismiss":
        if set(payload) != {"source_sha256", "confirmed", "note"} or payload.get("confirmed") is not True:
            return 400, {"error": "explicit confirmation and review reason are required"}
        note = payload.get("note")
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500:
            return 400, {"error": "please enter a 1–500 character review reason"}
        if not item["source_present"] or item["status"] not in {"pending", "authorized", "failed", "stale"}:
            return 409, {"error": "this anomaly cannot be dismissed in its current state"}
        try:
            event = _append_review_transition(data_dir, item, state, "dismissed",
                                              {"note": note.strip()})
        except (OSError, ValueError, FileExistsError) as exc:
            return 409, {"error": f"review decision was not saved: {exc}"}
        return 200, {"saved": True, "status": "dismissed", "review_event_id": event["event_id"]}

    if action == "authorize":
        if set(payload) - {"source_sha256", "proposal_sha256", "confirmed",
                           "confirm_completion", "note"} or not {
                "source_sha256", "proposal_sha256", "confirmed"} <= set(payload):
            return 400, {"error": "authorization requires source hash, proposal hash and confirmation"}
        if payload.get("confirmed") is not True:
            return 400, {"error": "explicit user authorization is required"}
        if item["status"] not in {"pending", "failed", "stale"} or not item["source_present"]:
            return 409, {"error": "anomaly is not awaiting authorization"}
        proposal = item.get("proposal")
        if not proposal or proposal["proposal_sha256"] != payload.get("proposal_sha256"):
            return 409, {"error": "repair proposal changed or is unsupported; refresh and inspect"}
        if (proposal["requires_completion_confirmation"]
                and payload.get("confirm_completion") is not True):
            return 400, {"error": "completion needs separate explicit user confirmation"}
        note = payload.get("note", "")
        if not isinstance(note, str) or len(note) > 500:
            return 400, {"error": "review note must be at most 500 characters"}
        current, stale_reason = _load_current_anomaly(data_dir, item)
        if current is None or current["source"]["sha256"] != item["source"]["sha256"]:
            return 409, {"error": stale_reason or "original event changed; refresh"}
        fresh_proposal = _build_review_proposal(data_dir, current, workspace)
        if not fresh_proposal or fresh_proposal["proposal_sha256"] != proposal["proposal_sha256"]:
            return 409, {"error": "target revision changed; refresh and review the new proposal"}
        approved = dict(proposal["event"])
        approved["timestamp"] = utc_now()
        try:
            if item["source"]["folder"] == "events":
                validate_event(approved)
            else:
                validate_step_event(approved)
            event = _append_review_transition(data_dir, item, state, "authorize", {
                "approved_event": approved, "proposal_sha256": proposal["proposal_sha256"],
                "note": note.strip(),
            })
        except (OSError, ValueError, FileExistsError) as exc:
            return 409, {"error": f"authorization was not saved: {exc}"}
        return 200, {"saved": True, "status": "authorized",
                     "review_event_id": event["event_id"],
                     "authorization_event_id": event["event_id"]}

    if action == "apply":
        if set(payload) != {"source_sha256", "authorization_event_id", "confirmed"}:
            return 400, {"error": "apply requires source hash, authorization event and confirmation"}
        if payload.get("confirmed") is not True:
            return 400, {"error": "explicit confirmation to execute the authorized write is required"}
        latest = state["latest"] if state else None
        if item["status"] == "applied":
            return 200, {"saved": False, "status": "applied",
                         "message": "the approved event has already been written and verified"}
        if item["status"] != "authorized" or not latest or latest["action"] != "authorize":
            return 409, {"error": "there is no current authorization to execute"}
        if latest["event_id"] != payload.get("authorization_event_id"):
            return 409, {"error": "authorization event changed; refresh before execution"}
        approved = latest["changes"]["approved_event"]
        current, stale_reason = _load_current_anomaly(data_dir, item)
        if current is None or current["source"]["sha256"] != item["source"]["sha256"]:
            try:
                _append_review_transition(data_dir, item, state, "stale",
                                          {"reason": stale_reason or "original source changed"})
            except (OSError, ValueError, FileExistsError):
                pass
            return 409, {"error": stale_reason or "original source changed; authorization is stale"}
        fresh_proposal = _build_review_proposal(data_dir, current, workspace)
        if (not fresh_proposal or
                fresh_proposal["proposal_sha256"] != latest["changes"]["proposal_sha256"]):
            try:
                _append_review_transition(data_dir, item, state, "stale",
                                          {"reason": "target revision or legal repair proposal changed"})
            except (OSError, ValueError, FileExistsError):
                pass
            return 409, {"error": "target revision changed; authorization is stale and must be reviewed again"}
        folder = item["source"]["folder"]
        validator = {"events": validate_event, "step_events": validate_step_event}.get(folder)
        if not validator:
            return 409, {"error": "this anomaly type cannot write automatically"}
        try:
            validator(approved)
            target_path = data_dir / folder / f"evt_{approved['event_id']}.json"
            if target_path.exists():
                existing = json.loads(target_path.read_text(encoding="utf-8-sig"))
                if existing != approved:
                    return 409, {"error": "target event ID already exists with different content"}
            else:
                _append_json_event(data_dir, approved, folder)
            written = json.loads(target_path.read_text(encoding="utf-8-sig"))
            if written != approved:
                raise ValueError("written event differs from the approved event")
            target_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
            verified_workspace = read_workspace(data_dir, include_trashed=True)
            verified_task = next((task for task in verified_workspace["tasks"]
                                  if task["task_id"] == approved["task_id"]), None)
            if not verified_task or verified_task.get("conflict"):
                raise ValueError("written event did not reduce to a conflict-free task")
            if folder == "step_events":
                verified_step = next((step for step in verified_task.get("steps", [])
                                      if step["step_id"] == approved["step_id"]), None)
                if not verified_step or verified_step.get("conflict"):
                    raise ValueError("written step event did not reduce to a conflict-free step")
                verified_revision = verified_step["revision"]
            else:
                verified_revision = verified_task["revision"]
            if verified_revision < approved["base_revision"] + 1:
                raise ValueError("result revision did not advance")
            result_event = _append_review_transition(data_dir, item, state, "applied", {
                "target_event_id": approved["event_id"], "target_folder": folder,
                "target_filename": target_path.name, "target_sha256": target_hash,
                "verified_revision": verified_revision,
            })
            return 200, {"saved": True, "status": "applied",
                         "target_event_id": approved["event_id"],
                         "verified_revision": verified_revision,
                         "review_event_id": result_event["event_id"]}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            # If the target event was already written, leave it in place. A retry
            # reuses the same deterministic event ID and completes the receipt.
            already_written = False
            try:
                if "target_path" in locals() and target_path.is_file():
                    already_written = json.loads(target_path.read_text(encoding="utf-8-sig")) == approved
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                already_written = False
            if not already_written:
                try:
                    _append_review_transition(data_dir, item, state, "failed",
                                              {"reason": str(exc)[:500]})
                except (OSError, ValueError, FileExistsError):
                    pass
            return 500, {"error": (
                f"approved event is already written but its result receipt is incomplete: {exc}; "
                "refresh and retry the same apply action"
                if already_written else
                f"write/result verification failed: {exc}; original source remains untouched"
            )}
    return 404, {"error": "unknown review action"}


def read_trash_retention(data_dir: Path) -> tuple[int, list[str]]:
    """Append-only shared settings; ambiguous same-second edits disable auto-purge."""
    directory = data_dir / "settings_events"
    items = []
    warnings = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > MAX_BODY:
                raise ValueError("settings file too large")
            event = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(event, dict) or event.get("version") != 1 or
                    not isinstance(event.get("event_id"), str) or
                    not EVENT_ID.fullmatch(event["event_id"]) or
                    event.get("key") != "trash_retention_days" or
                    type(event.get("days")) is not int or
                    event["days"] not in {0, 7, 30, 90}):
                raise ValueError("invalid shared trash retention setting")
            stamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("timezone required")
            items.append((stamp, event["days"], event["event_id"]))
        except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
            warnings.append(f"{path.name}: {exc}")
    if not items:
        return 30, warnings
    last = max(item[0] for item in items)
    values = {days for stamp, days, _ in items if stamp == last}
    if len(values) != 1:
        warnings.append("concurrent retention settings conflict; auto-purge disabled")
        return 0, warnings
    return next(iter(values)), warnings


def purge_local_task_history(data_dir: Path, task_id: str) -> int:
    """Best-effort local erase AFTER durable tombstone; other synced copies can return."""
    removed = 0
    for folder in ("events", "step_events"):
        directory = data_dir / folder
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in directory.glob("*.json"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                if path.stat().st_size > MAX_BODY:
                    continue
                entry = json.loads(path.read_text(encoding="utf-8-sig"))
                if (entry.get("task_id") != task_id or
                        (folder == "events" and entry.get("action") == "purge")):
                    continue
                path.unlink()
                removed += 1
            except (OSError, ValueError, TypeError, UnicodeError):
                continue
    return removed


def append_task_lifecycle(data_dir: Path, task: dict, action: str) -> dict:
    timestamp = utc_now()
    field = "purged_at" if action == "purge" else "trashed_at"
    value = None if action == "restore" else timestamp
    event = {"version": 1, "event_id": str(uuid.uuid4()),
             "task_id": task["task_id"], "action": action, "actor": "user",
             "timestamp": timestamp, "base_revision": task["revision"],
             "changes": {field: value}}
    append_event(data_dir, event)
    if action == "purge":
        purge_local_task_history(data_dir, task["task_id"])
    return event


def expire_trashed_tasks(data_dir: Path) -> None:
    """Sweep locally expired trashed tasks on workspace access, not while offline.

    A tombstone imported from another device hides the task, but MUST NOT
    independently erase local history. Only a local user's purge API or this
    local retention sweep may remove physical event files.
    """
    days, warnings = read_trash_retention(data_dir)
    if not days or warnings:
        return
    workspace = read_workspace(data_dir, include_trashed=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for task in workspace["tasks"]:
        if not task.get("trashed_at") or task.get("conflict"):
            continue
        if task.get("step_order_conflict") or task.get("step_order_incomplete"):
            continue
        try:
            stamp = datetime.fromisoformat(task["trashed_at"].replace("Z", "+00:00"))
            if stamp.tzinfo is not None and stamp <= cutoff:
                append_task_lifecycle(data_dir, task, "purge")
        except (ValueError, OSError):
            continue


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

        def read_payload(self) -> dict:
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise TypeError("JSON required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
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
                with _write_lock:
                    expire_trashed_tasks(data_dir)
                    workspace = read_workspace(data_dir)
                review_register = list_data_reviews(data_dir, workspace)
                workspace["review_summary"] = review_register["summary"]
                workspace["review_warnings"] = review_register["warnings"]
                return self.json_response(200, workspace)
            if path == "/api/reviews":
                with _write_lock:
                    workspace = read_workspace(data_dir, include_trashed=True)
                    register = list_data_reviews(data_dir, workspace)
                return self.json_response(200, register)
            if path == "/api/trash":
                with _write_lock:
                    expire_trashed_tasks(data_dir)
                    state = read_workspace(data_dir, include_trashed=True)
                    days, policy_warnings = read_trash_retention(data_dir)
                    trashed = [item for item in state["tasks"] if item.get("trashed_at")]
                return self.json_response(200, {
                    "tasks": trashed, "retention_days": days,
                    "warnings": state["warnings"] + policy_warnings
                })
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
            documents_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/documents", path)
            step_documents_match = re.fullmatch(
                r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/(STEP-[A-F0-9]{32})/documents", path)
            step_delete_match = re.fullmatch(
                r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/(STEP-[A-F0-9]{32})/delete", path)
            lifecycle_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/(trash|restore|purge)", path)
            changing_retention = path == "/api/trash/settings"
            review_match = re.fullmatch(
                r"/api/reviews/(ANOM-[A-F0-9]{32})/(authorize|apply|dismiss)", path)
            project_match = re.fullmatch(r"/api/projects/(PROJECT-[A-F0-9]{32})/update", path)
            step_create_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps", path)
            step_update_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/(STEP-[A-F0-9]{32})/update", path)
            step_reorder_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/steps/reorder", path)
            creating_task = path == "/api/tasks"
            creating_project = path == "/api/projects"
            applying_update = path == "/api/update/apply"
            if not (creating_task or creating_project or task_match or project_match or
                    step_create_match or step_update_match or step_reorder_match or
                    step_documents_match or step_delete_match or applying_update or
                    documents_match or lifecycle_match or changing_retention or review_match):
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
                payload = self.read_payload()
                if review_match:
                    with _write_lock:
                        code, result = perform_review_action(
                            data_dir, review_match.group(1), review_match.group(2), payload)
                    return self.json_response(code, result)

                if changing_retention:
                    if set(payload) != {"retention_days"} or type(payload["retention_days"]) is not int or payload["retention_days"] not in {0, 7, 30, 90}:
                        raise ValueError("retention_days must be 0, 7, 30 or 90")
                    with _write_lock:
                        record = {"version": 1, "event_id": str(uuid.uuid4()),
                                  "key": "trash_retention_days",
                                  "days": payload["retention_days"], "timestamp": utc_now()}
                        _append_json_event(data_dir, record, "settings_events")
                    return self.json_response(200, {"saved": True, "retention_days": payload["retention_days"]})

                if lifecycle_match:
                    action = lifecycle_match.group(2)
                    if set(payload) - {"revision", "confirmed_purge"} or "revision" not in payload:
                        raise ValueError("task lifecycle requires revision")
                    if type(payload["revision"]) is not int or payload["revision"] < 1:
                        raise ValueError("invalid task revision")
                    if action == "purge":
                        if payload.get("confirmed_purge") is not True:
                            raise ValueError("permanent deletion requires explicit confirmation")
                    elif "confirmed_purge" in payload:
                        raise ValueError("unexpected purge confirmation")
                    with _write_lock:
                        workspace = read_workspace(data_dir, include_trashed=True)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == lifecycle_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"] or task["revision"] != payload["revision"]:
                            return self.json_response(409, {"error": "task changed or has a conflict; refresh"})
                        if action == "trash" and task.get("trashed_at"):
                            return self.json_response(409, {"error": "task already in trash"})
                        if action != "trash" and not task.get("trashed_at"):
                            return self.json_response(409, {"error": "task must be in trash first"})
                        append_task_lifecycle(data_dir, task, action)
                    return self.json_response(200, {"saved": True, "action": action})

                if documents_match:
                    # Older task-scoped events remain readable so upgrades never lose
                    # references. New writes must target a concrete execution step.
                    return self.json_response(410, {
                        "error": "task-level document links are read-only legacy data; attach links to a step"
                    })

                if step_documents_match:
                    if set(payload) != {"revision", "links"}:
                        raise ValueError("step documents require revision and links")
                    revision = payload["revision"]
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid step revision")
                    links = validate_document_links(payload["links"])
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == step_documents_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"]:
                            return self.json_response(409, {"error": "task has a conflict; refresh"})
                        step = next((item for item in task.get("steps", [])
                                     if item["step_id"] == step_documents_match.group(2)), None)
                        if step is None:
                            return self.json_response(404, {"error": "step not found or deleted"})
                        if step["conflict"] or step["revision"] != revision:
                            return self.json_response(409, {"error": "step changed or has a conflict; refresh"})
                        if step.get("document_links", []) == links:
                            return self.json_response(200, {"saved": False, "revision": revision})
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task["task_id"], "step_id": step["step_id"],
                                 "action": "update", "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision,
                                 "changes": {"document_links": links}}
                        append_step_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "revision": revision + 1})

                if step_delete_match:
                    if set(payload) != {"revision", "confirmed_delete"} or payload["confirmed_delete"] is not True:
                        raise ValueError("step deletion requires revision and explicit confirmation")
                    revision = payload["revision"]
                    if type(revision) is not int or revision < 1:
                        raise ValueError("invalid step revision")
                    with _write_lock:
                        workspace = read_workspace(data_dir)
                        task = next((item for item in workspace["tasks"]
                                     if item["task_id"] == step_delete_match.group(1)), None)
                        if task is None:
                            return self.json_response(404, {"error": "task not found"})
                        if task["conflict"] or task.get("step_order_conflict") or task.get("step_order_incomplete"):
                            return self.json_response(409, {"error": "task or step order needs conflict review"})
                        step = next((item for item in task.get("steps", [])
                                     if item["step_id"] == step_delete_match.group(2)), None)
                        if step is None:
                            return self.json_response(404, {"error": "step not found or already deleted"})
                        if step["conflict"] or step["revision"] != revision:
                            return self.json_response(409, {"error": "step changed or has a conflict; refresh"})
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task["task_id"], "step_id": step["step_id"],
                                 "action": "delete", "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "confirmed_delete": True,
                                 "changes": {"deleted_at": utc_now()}}
                        append_step_event(data_dir, event)
                    return self.json_response(200, {"saved": True, "step_id": step["step_id"],
                                                    "deleted": True})

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
                    return self.json_response(201, {"saved": True, "task_id": task_id,
                                                    "display_id": display_task_id(task_id, event["timestamp"]),
                                                    "revision": 1})

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
