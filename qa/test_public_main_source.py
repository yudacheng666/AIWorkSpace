"""Post-merge real GitHub main source/install smoke test.

Runs on a GitHub-hosted Windows runner in a disposable application and
fictional data directory. Unlike updater E2E fixture tests, this test fetches
the real public GitHub main commit, raw VERSION and zipball. It NEVER accesses
company computers, real Drive data or any live user installation.

This is a QA-only test, not part of the product installer.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import zipfile
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import updater

EXPECTED_RELEASE_VERSION = "2.0.1"
EXPECTED_LEGACY_VERSION = "2.0.0"
LEGACY_MAIN_COMMIT = "fa51b0123aaac76ddff2064d34178e7cc6e3ab11"
EXPECTED_PUBLISHED_MAIN = "31963c3c48c9d9cd95663c971a55cb3bb9b108f6"
EVIDENCE_DIR = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "aiworkspace-main-source-smoke"


def snapshot(path: Path) -> dict[str, str]:
    return {
        child.relative_to(path).as_posix(): hashlib.sha256(child.read_bytes()).hexdigest()
        for child in path.rglob("*") if child.is_file()
    }


def install_real_previous_main(root: Path, files: tuple[str, ...]) -> None:
    """Seed actual V2.0.0 source from the pinned published GitHub main archive.

    Only four known application files are read; never extract untrusted paths.
    The main test then upgrades these bytes to real published V2.0.1.
    """
    old_url = (f"https://api.github.com/repos/yudacheng666/AIWorkSpace/"
               f"zipball/{LEGACY_MAIN_COMMIT}")
    archive_bytes = updater._read_url(old_url, updater.MAX_ARCHIVE_BYTES,
                                      timeout=30,
                                      allowed_hosts={"api.github.com", "codeload.github.com"})
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        self_roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(self_roots) != 1:
            raise AssertionError("published 2.0.0 archive has unexpected root paths")
        prefix = next(iter(self_roots)) + "/"
        for relative in files:
            entry = archive.getinfo(prefix + relative)
            mode = (entry.external_attr >> 16) & 0o170000
            if entry.is_dir() or mode == 0o120000:
                raise AssertionError("unsafe app entry in published 2.0.0 archive")
            payload = archive.read(entry)
            if len(payload) > updater.MAX_ENTRY_BYTES:
                raise AssertionError("published 2.0.0 entry too large")
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    if (root / "VERSION").read_text(encoding="utf-8").strip() != EXPECTED_LEGACY_VERSION:
        raise AssertionError("pinned legacy release is not V2.0.0")


@unittest.skipUnless(
    os.environ.get("AIWORKSPACE_RUN_LIVE_MAIN_SOURCE") == "1" and sys.platform == "win32",
    "isolated GitHub-hosted Windows live-source smoke only",
)
class PublishedMainSourceTests(unittest.TestCase):
    def test_real_public_main_download_validate_install_and_local_restart(self):
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="aiworkspace-live-main-") as temp:
            parent = Path(temp)
            root = parent / "application"
            data_dir = parent / "fictional-data"
            backup_dir = parent / "backup-outside-app-and-data"
            root.mkdir()
            data_dir.mkdir()
            files = ("app.py", "updater.py", "VERSION", "web/index.html")
            # Real official V2.0.0 source is the predecessor, not a newly
            # checked-out V2.0.1 app with VERSION spoofed backwards.
            install_real_previous_main(root, files)
            old_program_hashes = {
                relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
                for relative in files
            }
            for relative in ("events/fictional.bin", "project_events/fictional.bin",
                             "step_events/fictional.bin", "history.bin"):
                path = data_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("fictional-" + relative + "\n").encode("ascii"))
            original_data = snapshot(data_dir)

            latest = updater.check_latest_update(root)
            commit = latest["latest_commit"]
            self.assertRegex(commit, r"^[0-9a-f]{40}$")
            self.assertEqual(commit, EXPECTED_PUBLISHED_MAIN,
                             "main changed during post-merge validation")
            self.assertEqual(latest["latest_version"], EXPECTED_RELEASE_VERSION)
            self.assertTrue(latest["update_available"])
            self.assertFalse(latest["build_known"])
            print("Official GitHub main commit:", commit, flush=True)
            print("Official raw VERSION:", latest["latest_version"], flush=True)

            # These are three genuine public remote accesses:
            # API main -> raw VERSION at its commit -> zipball at that commit.
            # No monkeypatch, HTTP fixture, or alternate archive URL.
            stage, checked = updater.prepare_update(root, data_dir, commit)
            self.assertEqual(checked["latest_commit"], commit)
            staged_hashes = {}
            for relative in files:
                payload = (stage / relative).read_bytes()
                staged_hashes[relative] = hashlib.sha256(payload).hexdigest()
                # Git on Windows checks out .py/.html with CRLF, while the
                # public GitHub zipball retains LF. Compare the source text
                # after newline normalization; installed bytes stay original.
                checkout_bytes = (REPO / relative).read_bytes()
                self.assertEqual(payload.replace(b"\r\n", b"\n"),
                                 checkout_bytes.replace(b"\r\n", b"\n"),
                                 "live main archive does not match the shipping program: " + relative)

            self.assertEqual(snapshot(data_dir), original_data,
                             "download/staging changed fictional data files")
            backup = updater.apply_staged_update(root, data_dir, stage, commit,
                                                 backup_base=backup_dir)
            updater.remove_stage(stage)
            self.assertTrue((backup / "manifest.json").is_file())
            self.assertEqual((backup / "VERSION").read_bytes(), b"2.0.0\n")
            self.assertEqual(updater.get_install_status(root)["build_commit"], commit)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            log_file = EVIDENCE_DIR / "isolated-main-service.log"
            with log_file.open("w", encoding="utf-8") as output:
                server = subprocess.Popen(
                    [sys.executable, str(root / "app.py"), "--data-dir", str(data_dir),
                     "--port", str(port)],
                    cwd=str(root), stdout=output, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                )
                try:
                    deadline = time.monotonic() + 25
                    status = None
                    while time.monotonic() < deadline:
                        if server.poll() is not None:
                            self.fail("installed public main app exited instead of starting")
                        try:
                            with urlopen(f"http://127.0.0.1:{port}/api/update/status",
                                         timeout=1.5) as response:
                                status = json.loads(response.read().decode("utf-8"))
                            break
                        except (HTTPError, URLError, OSError, ValueError):
                            time.sleep(0.2)
                    self.assertIsNotNone(status, "installed main app never became ready")
                    self.assertEqual(status["version"], EXPECTED_RELEASE_VERSION)
                    self.assertEqual(status["build_commit"], commit)
                    self.assertTrue(status["build_known"])
                finally:
                    if server.poll() is None:
                        server.terminate()
                    try:
                        server.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=8)

            self.assertEqual(snapshot(data_dir), original_data,
                             "public main install/start modified fictional data files")
            # Prove the real V2.0.0 backup is usable without mutating user data.
            # Fault-injection/automatic service rollback already has separate
            # Windows Chromium CI coverage on the exact released product.
            updater.rollback_from_backup(root, data_dir, backup)
            self.assertEqual(updater.read_version(root), EXPECTED_LEGACY_VERSION)
            for relative, expected_hash in old_program_hashes.items():
                self.assertEqual(
                    hashlib.sha256((root / relative).read_bytes()).hexdigest(),
                    expected_hash, "rollback did not restore V2.0.0: " + relative)
            self.assertFalse(updater.get_install_status(root)["build_known"])
            self.assertEqual(snapshot(data_dir), original_data,
                             "rollback touched fictional data files")
            evidence = {
                "result": "PASS",
                "legacy_main_commit": LEGACY_MAIN_COMMIT,
                "legacy_version": EXPECTED_LEGACY_VERSION,
                "rollback_to_2_0_0": True,
                "simulated_company_data": False,
                "source": "real public GitHub main; NO mock/fixture",
                "commit": commit,
                "version": EXPECTED_RELEASE_VERSION,
                "app_status": {"version": status["version"], "build_commit": status["build_commit"]},
                "program_file_sha256": staged_hashes,
                "fictional_data_sha256": original_data,
                "backup_manifest_exists": True,
            }
            (EVIDENCE_DIR / "public-main-source-result.json").write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
