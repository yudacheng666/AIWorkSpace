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
    if set(changes) - {"title", "status"}:
        raise ValueError("unknown fields")
    if "title" in changes and (not isinstance(changes["title"], str)
                               or not 1 <= len(changes["title"].strip()) <= 200):
        raise ValueError("title must be 1–200 characters")
    if "status" in changes and changes["status"] not in STATUSES:
        raise ValueError("invalid status")
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


def read_workspace(data_dir: Path) -> dict:
    """Reduce independent event files; never silently choose a concurrent edit."""
    event_dir = data_dir / "events"
    created: dict[str, list[dict]] = defaultdict(list)
    updated: dict[str, list[dict]] = defaultdict(list)
    warnings: list[str] = []
    seen: set[str] = set()
    if not event_dir.exists():
        return {"tasks": [], "warnings": []}

    for path in sorted(event_dir.glob("*.json")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BODY:
                raise ValueError("file too large")
            event = validate_event(json.loads(path.read_text(encoding="utf-8")))
            if event["event_id"] in seen:
                raise ValueError("duplicate event_id")
            seen.add(event["event_id"])
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
    return {"tasks": tasks, "warnings": warnings}


def append_event(data_dir: Path, event: dict) -> Path:
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
        if destination.exists():
            raise FileExistsError("event already exists")
        os.replace(temp_name, destination)
        temp_name = None
        return destination
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def handler_factory(data_dir: Path):
    class Handler(BaseHTTPRequestHandler):
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

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/tasks":
                return self.json_response(200, read_workspace(data_dir))
            if path in {"/", "/index.html"}:
                return self.respond(200, (ROOT / "web" / "index.html").read_bytes(),
                                    "text/html; charset=utf-8")
            return self.json_response(404, {"error": "not found"})

        def do_POST(self):
            path = unquote(urlsplit(self.path).path)
            match = re.fullmatch(r"/api/tasks/(TASK-[A-Za-z0-9-]{1,50})/update", path)
            if not match:
                return self.json_response(404, {"error": "not found"})
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if not host.startswith(("127.0.0.1:", "localhost:")) or (
                origin and origin not in {f"http://{host}"}
            ):
                return self.json_response(403, {"error": "local requests only"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.json_response(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("invalid body length")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
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
                    tasks = {t["task_id"]: t for t in read_workspace(data_dir)["tasks"]}
                    current = tasks.get(match.group(1))
                    if not current:
                        return self.json_response(404, {"error": "task not found"})
                    if current["conflict"] or current["revision"] != revision:
                        return self.json_response(409, {"error": "task changed or has a conflict; refresh"})
                    event = {"version": 1, "event_id": str(uuid.uuid4()),
                             "task_id": current["task_id"], "action": "update",
                             "actor": "user", "timestamp": utc_now(),
                             "base_revision": revision,
                             "changes": {"title": title.strip(), "status": status}}
                    if status == "done":
                        event["confirmed_done"] = True
                    append_event(data_dir, event)
                return self.json_response(200, {"saved": True, "task_id": match.group(1)})
            except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                return self.json_response(400, {"error": str(exc)})
            except OSError:
                return self.json_response(500, {"error": "unable to save event"})

        def log_message(self, format_string, *args):
            # Do not print URLs, post bodies, or task data into runtime logs.
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
