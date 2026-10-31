"""Real Windows end-to-end updater tests using the shipped app and Chromium.

The test runs only on an isolated GitHub-hosted Windows runner. It copies the
actual checkout into a temporary install directory, creates fictional data,
and intercepts the updater's fixed GitHub HTTPS endpoints inside child
processes. No real GitHub release, Google Drive, or company service is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path

try:
    import psutil
except ImportError:  # Installed explicitly by the dedicated GitHub Actions job.
    psutil = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "c" * 40
LATEST_VERSION = "1.0.1"
API_URL = "https://api.github.com/repos/yudacheng666/AIWorkSpace/commits/main"
RAW_PREFIX = "https://raw.githubusercontent.com/yudacheng666/AIWorkSpace/"
ARCHIVE_URL = f"https://api.github.com/repos/yudacheng666/AIWorkSpace/zipball/{COMMIT}"
APP_FILES = ("app.py", "updater.py", "VERSION", "web/index.html")

# Loaded by sitecustomize in the actual app, helper, and restarted app processes.
# Unknown HTTPS requests are blocked, while the helper's loopback health checks
# are passed through to the real local HTTP server.
SITECUSTOMIZE = r'''
import json
import os
from pathlib import Path
import urllib.request
from urllib.error import URLError

_real_urlopen = urllib.request.urlopen
_config_path = os.environ.get("AIWORKSPACE_UPDATE_E2E_FIXTURE")
if not _config_path:
    raise RuntimeError("missing isolated updater fixture")
_config = json.loads(Path(_config_path).read_text(encoding="utf-8"))
_trace_path = Path(os.environ["AIWORKSPACE_UPDATE_E2E_TRACE"])

class _FixtureResponse:
    def __init__(self, body, url):
        self._body = body
        self._url = url
        self.headers = {"Content-Length": str(len(body))}
    def read(self, size=-1):
        return self._body if size is None or size < 0 else self._body[:size]
    def geturl(self):
        return self._url
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False

def _record(url):
    with _trace_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"url": url}) + "\n")

def _fixture_urlopen(request, *args, **kwargs):
    url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
    if url == "https://api.github.com/repos/yudacheng666/AIWorkSpace/commits/main":
        _record(url)
        body = json.dumps({
            "sha": _config["commit"],
            "commit": {
                "message": "isolated Windows updater end-to-end fixture",
                "committer": {"date": "2026-10-30T00:00:00Z"}
            }
        }).encode("utf-8")
        return _FixtureResponse(body, url)
    if url == "https://raw.githubusercontent.com/yudacheng666/AIWorkSpace/" + _config["commit"] + "/VERSION":
        _record(url)
        return _FixtureResponse((_config["version"] + "\n").encode("utf-8"), url)
    if url == "https://api.github.com/repos/yudacheng666/AIWorkSpace/zipball/" + _config["commit"]:
        _record(url)
        return _FixtureResponse(Path(_config["archive_path"]).read_bytes(), url)
    if url.startswith("http://127.0.0.1:"):
        return _real_urlopen(request, *args, **kwargs)
    raise URLError("only the fixed GitHub fixture and loopback HTTP are allowed in this test")

urllib.request.urlopen = _fixture_urlopen
'''


@unittest.skipUnless(
    sys.platform == "win32"
    and os.environ.get("AIWORKSPACE_RUN_WINDOWS_E2E") == "1"
    and sync_playwright is not None
    and psutil is not None,
    "dedicated isolated Windows + Playwright job only",
)
class WindowsUpdaterBrowserE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiworkspace-update-e2e-")
        self.base = Path(self.temp.name)
        self.root = self.base / "application"
        self.data_dir = self.base / "fictional-data"
        self.fixture_dir = self.base / "python-fixture"
        self.home_dir = self.base / "isolated-user-profile"
        self.evidence_dir = Path(os.environ.get("RUNNER_TEMP", str(self.base))) / "aiworkspace-update-e2e"
        self.root.mkdir()
        self.data_dir.mkdir()
        self.fixture_dir.mkdir()
        self.home_dir.mkdir()
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        for relative in APP_FILES:
            source = REPO_ROOT / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        (self.root / "VERSION").write_bytes(b"1.0.0\n")
        for name in (".aiworkspace-build.json", ".aiworkspace-update-state.json"):
            (self.root / name).unlink(missing_ok=True)

        # These are deliberately non-JSON sentinels: the application will not
        # load them as events, but the test can prove every byte stays intact.
        sentinels = {
            "events/fictional-events.bin": b"fictional event data must remain byte-identical\n",
            "project_events/fictional-projects.bin": b"fictional project data must remain byte-identical\n",
            "step_events/fictional-steps.bin": b"fictional step data must remain byte-identical\n",
            "history.bin": b"fictional history must remain byte-identical\n",
        }
        for relative, content in sentinels.items():
            target = self.data_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        self.data_snapshot = self._snapshot_data()
        self.old_files = {relative: (self.root / relative).read_bytes() for relative in APP_FILES}

        self.archive_path = self.base / "github-main-fixture.zip"
        self.trace_path = self.evidence_dir / (self._testMethodName + "-github-mock-network.jsonl")
        self.trace_path.unlink(missing_ok=True)
        self.fixture_config_path = self.base / "github-fixture.json"
        (self.fixture_dir / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        self.fixture_config_path.write_text(json.dumps({
            "commit": COMMIT,
            "version": LATEST_VERSION,
            "archive_path": str(self.archive_path),
        }), encoding="utf-8")

        self.env = os.environ.copy()
        old_pythonpath = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(self.fixture_dir) + (os.pathsep + old_pythonpath if old_pythonpath else "")
        self.env["AIWORKSPACE_UPDATE_E2E_FIXTURE"] = str(self.fixture_config_path)
        self.env["AIWORKSPACE_UPDATE_E2E_TRACE"] = str(self.trace_path)
        self.env["USERPROFILE"] = str(self.home_dir)
        self.env["HOME"] = str(self.home_dir)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]

        self.old_process = None
        self.service_log = None
        self.service_log_path = None
        self.addCleanup(self._cleanup)

    def _snapshot_data(self):
        return {
            path.relative_to(self.data_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.data_dir.rglob("*")
            if path.is_file()
        }

    def _assert_data_unchanged(self):
        self.assertEqual(self._snapshot_data(), self.data_snapshot,
                         "update or rollback modified fictional data-dir files")

    def _write_archive(self, failing_new_app=False):
        files = {relative: (self.root / relative).read_bytes() for relative in APP_FILES}
        files["VERSION"] = (LATEST_VERSION + "\n").encode("utf-8")
        if failing_new_app:
            # Valid Python that exits immediately after the helper installs it.
            # The real old app must be restored and restarted by updater.py.
            files["app.py"] = b"import sys\nsys.exit(17)\n"

        prefix = "yudacheng666-AIWorkSpace-" + COMMIT[:7]
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, content in files.items():
                archive.writestr(prefix + "/" + relative, content)

    def _start_old_service(self):
        self.service_log_path = self.evidence_dir / ("windows-service-" + self._scenario + ".log")
        self.service_log = self.service_log_path.open("w", encoding="utf-8")
        self.old_process = subprocess.Popen(
            [sys.executable, str(self.root / "app.py"),
             "--data-dir", str(self.data_dir), "--port", str(self.port)],
            cwd=str(self.root),
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=self.service_log,
            stderr=subprocess.STDOUT,
        )
        self._wait_for_status()
        self.assertEqual(self._get_status()["version"], "1.0.0")

    def _get_status(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/api/update/status", timeout=2
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def _wait_for_status(self, timeout=20):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            if self.old_process is not None and self.old_process.poll() not in (None, 0):
                raise AssertionError(f"old app process exited unexpectedly: {self.old_process.returncode}")
            try:
                return self._get_status()
            except (OSError, ValueError) as exc:
                last_error = exc
                time.sleep(0.2)
        raise AssertionError(f"isolated app did not become ready: {last_error}")

    def _assert_backup(self):
        backup_root = self.home_dir / ".aiworkspace" / "update-backups"
        backups = sorted((path for path in backup_root.glob("*") if path.is_dir()),
                         key=lambda path: path.stat().st_mtime)
        self.assertTrue(backups, "updater did not create an external backup")
        backup = backups[-1]
        self.assertFalse(backup.resolve().is_relative_to(self.root.resolve()))
        self.assertFalse(backup.resolve().is_relative_to(self.data_dir.resolve()))
        self.assertEqual((backup / "VERSION").read_bytes(), self.old_files["VERSION"])
        self.assertTrue((backup / "manifest.json").is_file())
        return backup

    def _run_browser_update(self, scenario, expect_rollback):
        self._scenario = scenario
        self._write_archive(failing_new_app=expect_rollback)
        self._start_old_service()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            trace_path = self.evidence_dir / (scenario + "-playwright-trace.zip")
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.accept())
            try:
                page.goto(f"http://127.0.0.1:{self.port}/", wait_until="domcontentloaded", timeout=30000)
                # Update controls now live on the dedicated System Settings page.
                page.locator("#nav-settings").click()
                page.locator("#app-version").wait_for(timeout=15000)
                self.assertIn("v1.0.0", page.locator("#app-version").inner_text())

                page.locator("#check-update").click()
                page.locator("#apply-update").wait_for(state="visible", timeout=15000)
                self.assertIn("发现新版本 v1.0.1", page.locator("#update-message").inner_text())

                page.locator("#apply-update").click()
                if expect_rollback:
                    page.wait_for_function(
                        "() => document.querySelector('#update-message')?.textContent.includes('已自动恢复旧版本')",
                        timeout=60000,
                    )
                    status = self._wait_for_status(timeout=15)
                    self.assertEqual(status["version"], "1.0.0")
                    self.assertIsNone(status["build_commit"])
                    self.assertEqual(status["last_update"]["status"], "rolled_back")
                    self.assertIsNotNone(self.old_process.poll(),
                                         "old service process did not exit before rollback restart")
                    self.assertEqual((self.root / "VERSION").read_bytes(), self.old_files["VERSION"])
                    for relative, content in self.old_files.items():
                        self.assertEqual((self.root / relative).read_bytes(), content,
                                         f"rollback did not restore {relative}")
                    self.assertIn("v1.0.0", page.locator("#app-version").inner_text())
                else:
                    page.wait_for_function(
                        "() => document.querySelector('#app-version')?.textContent.includes('v1.0.1') && "
                        "document.querySelector('#app-version')?.textContent.includes('" + COMMIT[:7] + "')",
                        timeout=60000,
                    )
                    status = self._wait_for_status(timeout=15)
                    self.assertEqual(status["version"], LATEST_VERSION)
                    self.assertEqual(status["build_commit"], COMMIT)
                    self.assertEqual(status["build_known"], True)
                    self.assertEqual((self.root / "VERSION").read_text(encoding="utf-8").strip(), LATEST_VERSION)
                    self.assertIn("v1.0.1", page.locator("#app-version").inner_text())
                    self.assertIsNotNone(self.old_process.poll(),
                                         "old service process did not exit during update")

                backup = self._assert_backup()
                shutil.copy2(backup / "manifest.json",
                             self.evidence_dir / (scenario + "-backup-manifest.json"))
                self._assert_data_unchanged()
                traced_urls = {
                    json.loads(line)["url"]
                    for line in self.trace_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
                self.assertIn(API_URL, traced_urls)
                self.assertIn(RAW_PREFIX + COMMIT + "/VERSION", traced_urls)
                self.assertIn(ARCHIVE_URL, traced_urls)
                (self.evidence_dir / (scenario + "-result.json")).write_text(
                    json.dumps({
                        "scenario": scenario,
                        "result": "PASS",
                        "version": status["version"],
                        "build_commit": status["build_commit"],
                        "last_update": status["last_update"],
                        "data_files_sha256": self.data_snapshot,
                        "external_backup_created": True,
                        "github_requests_intercepted": sorted(traced_urls),
                    }, indent=2),
                    encoding="utf-8",
                )
            finally:
                try:
                    page.screenshot(path=str(self.evidence_dir / (scenario + ".png")), full_page=True)
                except Exception:
                    pass
                try:
                    context.tracing.stop(path=str(trace_path))
                except Exception:
                    pass
                browser.close()

    def test_real_app_browser_one_click_update_restarts_on_same_port_and_preserves_data(self):
        self._run_browser_update("success", expect_rollback=False)

    def test_real_app_browser_failed_new_build_rolls_back_and_restarts_old_version(self):
        self._run_browser_update("rollback", expect_rollback=True)

    def _cleanup(self):
        # Stop only processes whose command line points into this unique temp
        # installation or which own this test's ephemeral loopback port.
        if psutil is not None:
            root_text = str(self.root).casefold()
            pids = set()
            try:
                for connection in psutil.net_connections(kind="tcp"):
                    if (connection.laddr and connection.laddr.port == self.port
                            and connection.status == psutil.CONN_LISTEN and connection.pid):
                        pids.add(connection.pid)
            except (OSError, psutil.Error):
                pass
            for process in psutil.process_iter(["pid", "cmdline"]):
                try:
                    command = " ".join(process.info.get("cmdline") or []).casefold()
                    if root_text in command:
                        pids.add(process.info["pid"])
                except (OSError, psutil.Error):
                    continue
            processes = []
            for pid in pids:
                if pid == os.getpid():
                    continue
                try:
                    process = psutil.Process(pid)
                    process.terminate()
                    processes.append(process)
                except (OSError, psutil.Error):
                    continue
            if processes:
                psutil.wait_procs(processes, timeout=8)
                for process in processes:
                    try:
                        if process.is_running():
                            process.kill()
                    except (OSError, psutil.Error):
                        pass

        if self.old_process is not None and self.old_process.poll() is None:
            self.old_process.kill()
            self.old_process.wait(timeout=8)
        if self.service_log is not None:
            self.service_log.flush()
            self.service_log.close()
        self.temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
