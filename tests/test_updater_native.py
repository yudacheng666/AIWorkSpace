"""Native Windows helper lifecycle checks with fully isolated fictional data.

These tests launch actual Python processes on GitHub's Windows runner, not the
company's service or a real Google Drive directory.  GitHub HTTP is never used.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater

COMMIT = "b" * 40

# A deliberately small local HTTP fixture isolates native helper process,
# file locks, rollback and port/data-dir preservation from application APIs.
STUB = """import argparse, json, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
p = argparse.ArgumentParser()
p.add_argument("--port", type=int, required=True)
p.add_argument("--data-dir", type=Path, required=True)
args = p.parse_args()
root = Path(__file__).resolve().parent
(root / "native-server.pid").write_text(str(os.getpid()), encoding="ascii")
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/update/status":
            self.send_response(404)
            self.end_headers()
            return
        build_path = root / ".aiworkspace-build.json"
        build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.exists() else {}
        payload = json.dumps({"version": (root / "VERSION").read_text(encoding="utf-8").strip(),
                              "build_commit": build.get("commit"),
                              "data_dir_ok": args.data_dir.exists()}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *_args):
        pass
s = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
try:
    s.serve_forever()
finally:
    s.server_close()
"""

@unittest.skipUnless(sys.platform == "win32", "native Windows lifecycle only")
class NativeWindowsUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "app"
        self.root.mkdir()
        (self.root / "web").mkdir()
        self.data = self.base / "data"
        for name in ("events", "project_events", "step_events"):
            folder = self.data / name
            folder.mkdir(parents=True)
            (folder / "fictional.json").write_bytes(
                b'{"fictional":"immutable native test data"}\\n')
        self.data_bytes = {p.relative_to(self.data).as_posix(): p.read_bytes()
                           for p in self.data.rglob("*") if p.is_file()}
        self.root.joinpath("app.py").write_text(STUB + "\\n# old-version\\n", encoding="utf-8")
        self.root.joinpath("updater.py").write_bytes(Path(updater.__file__).read_bytes())
        self.root.joinpath("VERSION").write_text("0.9.0\\n", encoding="utf-8")
        self.root.joinpath("web/index.html").write_text("<p>old</p>", encoding="utf-8")
        self.stage = self.root / ".aiworkspace-update-staging-native"
        (self.stage / "web").mkdir(parents=True)
        self.stage.joinpath("app.py").write_text(STUB + "\\n# new-version\\n", encoding="utf-8")
        self.stage.joinpath("updater.py").write_bytes(Path(updater.__file__).read_bytes())
        self.stage.joinpath("VERSION").write_text("1.0.0\\n", encoding="utf-8")
        self.stage.joinpath("web/index.html").write_text("<p>new</p>", encoding="utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.old = None
        self.helper = None

    def tearDown(self):
        for proc in (self.helper, self.old):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=8)
        pid_file = self.root / "native-server.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="ascii").strip())
                # This is a PID obtained from the isolated new fixture.
                if pid not in {os.getpid(), getattr(self.old, "pid", -1)}:
                    os.kill(pid, signal.SIGTERM)
            except (OSError, ValueError, ProcessLookupError):
                pass
        self.temp.cleanup()

    def _status(self, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urlopen(f"http://127.0.0.1:{self.port}/api/update/status", timeout=0.5) as r:
                    return json.loads(r.read().decode("utf-8"))
            except (URLError, OSError, ValueError):
                time.sleep(0.1)
        raise AssertionError("isolated Windows test service did not become ready")

    def _start_old(self):
        self.old = subprocess.Popen(
            [sys.executable, str(self.root / "app.py"), "--data-dir", str(self.data),
             "--port", str(self.port)],
            cwd=str(self.root), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertEqual(self._status()["version"], "0.9.0")

    def _launch_and_finish(self):
        self.helper = updater.launch_update_helper(
            self.stage, self.root, self.data, COMMIT, self.port, self.old.pid)
        self.old.terminate()
        self.old.wait(timeout=8)
        return self.helper.wait(timeout=60)

    def _assert_data(self):
        present = {p.relative_to(self.data).as_posix(): p.read_bytes()
                   for p in self.data.rglob("*") if p.is_file()}
        self.assertEqual(present, self.data_bytes,
                         "native helper must never modify any data-dir file")

    def test_native_windows_helper_restarts_service_and_preserves_port_and_data(self):
        self._start_old()
        self.assertEqual(self._launch_and_finish(), 0, "helper failed to restart new build")
        current = self._status()
        self.assertEqual(current["version"], "1.0.0")
        self.assertEqual(current["build_commit"], COMMIT)
        self.assertTrue(current["data_dir_ok"])
        self.assertIn("# new-version", (self.root / "app.py").read_text(encoding="utf-8"))
        self.assertEqual(updater.get_install_status(self.root)["build_commit"], COMMIT)
        self._assert_data()

    def test_native_windows_failed_start_restores_old_program_and_service(self):
        self.stage.joinpath("app.py").write_text(
            "import sys\\nsys.exit(17)\\n", encoding="utf-8")
        self._start_old()
        self.assertEqual(self._launch_and_finish(), 1,
                         "failed new server must fail and restore old version")
        current = self._status()
        self.assertEqual(current["version"], "0.9.0")
        self.assertIsNone(current["build_commit"])
        self.assertIn("# old-version", (self.root / "app.py").read_text(encoding="utf-8"))
        self.assertEqual(updater.get_install_status(self.root)["last_update"]["status"], "rolled_back")
        self._assert_data()
