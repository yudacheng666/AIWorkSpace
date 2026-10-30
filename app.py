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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
TASK_ID = re.compile(r"^TASK-[A-Za-z0-9-]{1,50}$")
PROJECT_ID = re.compile(r"^PROJECT-[A-F0-9]{32}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9-]{8,80}$")
STATUSES = {"todo", "doing", "blocked", "done"}
MAX_BODY = 16_384
_write_lock = threading.Lock()


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
    if set(changes) - {"title", "status", "project_id", "related_project_ids"}:
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
    """Fields whose candidate values differ across conflicting events."""
    fields = {field for event in events for field in event["changes"]}
    return sorted(
        field for field in fields
        if len({event["changes"].get(field) for event in events}) > 1
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
        return {"tasks": [], "projects": project_state["projects"], "warnings": project_state["warnings"]}

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
        task = {"task_id": task_id, "title": roots[0]["changes"]["title"].strip(),
                "status": "todo", "revision": 1, "conflict": False,
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
        task.setdefault("project_id", None)
        task.setdefault("related_project_ids", [])
        primary = project_map.get(task["project_id"]) if task["project_id"] else None
        task["project_name"] = primary["name"] if primary and not primary["conflict"] else None
        task["project_missing"] = bool(task["project_id"] and primary is None)
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


def validate_project_references(workspace: dict, project_id: object,
                                related_project_ids: object) -> None:
    projects = {project["project_id"]: project for project in workspace["projects"]}
    if project_id is not None:
        project = projects.get(project_id)
        if not project or project["conflict"]:
            raise ValueError("primary project does not exist or needs conflict review")
    if not isinstance(related_project_ids, list):
        raise ValueError("related_project_ids must be a list")
    if len(related_project_ids) > 20 or len(set(related_project_ids)) != len(related_project_ids):
        raise ValueError("invalid related_project_ids")
    if project_id in related_project_ids:
        raise ValueError("primary project cannot also be a related project")
    for related_id in related_project_ids:
        project = projects.get(related_id)
        if not isinstance(related_id, str) or not PROJECT_ID.fullmatch(related_id) or not project or project["conflict"]:
            raise ValueError("related project does not exist or needs conflict review")

    """Publish one complete JSON file with a random name; never edit live data."""
    validate_event(event)
    directory = data_dir / "events"
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
        # Hard-link publication is atomic and refuses to replace an existing event.
        # Unlike os.replace(), concurrent writers cannot silently overwrite each other.
        try:
            os.link(temp_name, destination)
        except FileExistsError:
            raise FileExistsError("event already exists") from None
        published_temp = temp_name
        temp_name = None
        try:
            os.unlink(published_temp)
        except OSError:
            # The event is already published; a leftover .part file is ignored by readers.
            pass
        return destination
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


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
                return self.json_response(200, read_workspace(data_dir))
            if path in {"/", "/index.html"}:
                return self.respond(200, (ROOT / "web" / "index.html").read_bytes(),
                                    "text/html; charset=utf-8")
            return self.json_response(404, {"error": "not found"})

        def do_POST(self):
            path = unquote(urlsplit(self.path).path)
            task_match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/update", path)
            project_match = re.fullmatch(r"/api/projects/(PROJECT-[A-F0-9]{32})/update", path)
            creating_task = path == "/api/tasks"
            creating_project = path == "/api/projects"
            if not (creating_task or creating_project or task_match or project_match):
                return self.json_response(404, {"error": "not found"})
            if not self.local_request_allowed():
                return self.json_response(403, {"error": "local requests only"})
            try:
                payload = self.read_payload()
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
                    if set(payload) - {"title", "project_id", "related_project_ids"}:
                        raise ValueError("new task accepts title and project references only")
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
                        if "project_id" in payload:
                            changes["project_id"] = project_id
                        if "related_project_ids" in payload:
                            changes["related_project_ids"] = related_ids
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": task_id, "action": "create",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": 0, "changes": changes}
                        append_event(data_dir, event)
                    return self.json_response(201, {"saved": True, "task_id": task_id, "revision": 1})

                if task_match:
                    allowed = {"title", "status", "revision", "project_id",
                               "related_project_ids", "confirmed_done"}
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
                        if "project_id" in payload or "related_project_ids" in payload:
                            project_id = payload.get("project_id", current.get("project_id"))
                            related_ids = payload.get("related_project_ids", current.get("related_project_ids", []))
                            validate_project_references(workspace, project_id, related_ids)
                            if "project_id" in payload:
                                changes["project_id"] = project_id
                            if "related_project_ids" in payload:
                                changes["related_project_ids"] = related_ids
                        event = {"version": 1, "event_id": str(uuid.uuid4()),
                                 "task_id": current["task_id"], "action": "update",
                                 "actor": "user", "timestamp": utc_now(),
                                 "base_revision": revision, "changes": changes}
                        if status == "done":
                            event["confirmed_done"] = True
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
