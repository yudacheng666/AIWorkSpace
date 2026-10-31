"""Run the unmodified AIWorkSpace application in an isolated local-only temporary directory.

This launcher uses Python's standard library only. It never reads an existing
user data directory and never changes the original app.py or business files.
"""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ("app.py", "updater.py", "VERSION", "web/index.html")


def verify_bundle() -> None:
    missing = [name for name in ALLOWED if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError("Missing preview application files: " + ", ".join(missing))


def temporary_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Start isolated AIWorkSpace V2 UI preview")
    parser.add_argument("--check", action="store_true", help="Verify bundle without running")
    args = parser.parse_args()
    verify_bundle()
    if args.check:
        print("PASS: preview bundle contains the expected application files.")
        return

    # Nothing is copied from an existing Drive or company data directory.
    with tempfile.TemporaryDirectory(prefix="AIWorkSpace-V2-Preview-") as temp:
        target = Path(temp)
        for name in ALLOWED:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        data = target / "test-data-only"
        data.mkdir()
        port = temporary_port()
        url = f"http://127.0.0.1:{port}/"
        command = [sys.executable, str(target / "app.py"), "--data-dir",
                   str(data), "--port", str(port)]
        log = (target / "server.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=str(target), stdout=log,
                                stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                if proc.poll() is not None:
                    raise RuntimeError("The test service exited before startup.")
                try:
                    with urllib.request.urlopen(url, timeout=0.3) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("The isolated service did not respond.")

            print("=" * 62)
            print("AIWorkSpace UI V2 — ISOLATED TEST ONLY")
            print("URL:", url)
            print("Test files:", data)
            print("This is NOT the installed workbench or real Drive data.")
            print("Do not use the Software Update function during preview.")
            print("Press Enter to close the server and DELETE temporary test data.")
            print("=" * 62)
            webbrowser.open(url)
            input()
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            log.close()


if __name__ == "__main__":
    main()
