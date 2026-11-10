from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop_launcher
from app import handler_factory


class DesktopLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "application"
        self.root.mkdir()
        (self.root / "app.py").write_text("# isolated app fixture\n", encoding="utf-8")
        self.data = self.base / "AIWorkSpaceData"
        (self.data / "events").mkdir(parents=True)
        self.home = self.base / "local-app-data"
        self.env_patch = patch.dict(
            os.environ, {"AIWORKSPACE_LAUNCHER_HOME": str(self.home)}
        )
        self.env_patch.start()
        self.config = self.home / "launcher.json"
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            json.dumps({"data_dir": str(self.data), "port": self.free_port()}),
            encoding="utf-8",
        )
        self.server = None
        self.server_thread = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread is not None:
            self.server_thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def start_test_server(self, token):
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            handler_factory(self.data, control_token=token),
        )

        def serve():
            try:
                self.server.serve_forever()
            finally:
                self.server.server_close()

        self.server_thread = threading.Thread(target=serve, daemon=True)
        self.server_thread.start()
        return self.server.server_port

    def write_service_state(self, port, token):
        state_dir = desktop_launcher.runtime_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "service.json").write_text(
            json.dumps({
                "service": "AIWorkSpace",
                "pid": 12345,
                "port": port,
                "token": token,
            }),
            encoding="utf-8",
        )

    def test_load_config_preserves_existing_data_root_and_port(self):
        config = desktop_launcher.load_config(self.root, self.config)
        self.assertEqual(config["data_dir"], self.data.resolve())
        self.assertEqual(config["port"], json.loads(self.config.read_text())["port"])

    def test_load_config_rejects_events_subfolder(self):
        config_file = self.home / "events.json"
        config_file.write_text(
            json.dumps({"data_dir": str(self.data / "events"), "port": 8770}),
            encoding="utf-8",
        )
        with self.assertRaises(desktop_launcher.LauncherError):
            desktop_launcher.load_config(self.root, config_file)

    def test_load_config_rejects_data_folder_inside_program_folder(self):
        nested = self.root / "private-data"
        nested.mkdir()
        config_file = self.home / "nested.json"
        config_file.write_text(
            json.dumps({"data_dir": str(nested), "port": 8770}), encoding="utf-8"
        )
        with self.assertRaises(desktop_launcher.LauncherError):
            desktop_launcher.load_config(self.root, config_file)

    def test_start_reuses_existing_service_without_spawning_a_second_process(self):
        with (
            patch.object(desktop_launcher, "identify_existing_service", return_value="current"),
            patch.object(desktop_launcher.webbrowser, "open_new_tab", return_value=True),
            patch.object(desktop_launcher.subprocess, "Popen") as popen,
        ):
            result = desktop_launcher.start(self.root, self.config)
        self.assertEqual(result, "already_running")
        popen.assert_not_called()

    def test_legacy_service_is_detected_and_reused_without_duplicate_start(self):
        class LegacyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/api/update/status":
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = json.dumps({
                    "version": "2.9.1",
                    "build_commit": None,
                    "build_known": False,
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LegacyHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.config.write_text(
            json.dumps({"data_dir": str(self.data), "port": self.server.server_port}),
            encoding="utf-8",
        )
        with (
            patch.object(desktop_launcher.webbrowser, "open_new_tab", return_value=True),
            patch.object(desktop_launcher.subprocess, "Popen") as popen,
        ):
            result = desktop_launcher.start(self.root, self.config)
        self.assertEqual(result, "legacy_running")
        popen.assert_not_called()

    def test_start_refuses_a_port_owned_by_another_program(self):
        with (
            patch.object(desktop_launcher, "identify_existing_service", return_value=None),
            patch.object(desktop_launcher, "port_in_use", return_value=True),
            patch.object(desktop_launcher.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(desktop_launcher.LauncherError):
                desktop_launcher.start(self.root, self.config)
        popen.assert_not_called()

    def test_start_waits_for_health_before_opening_browser(self):
        process = Mock()
        process.poll.return_value = None
        with (
            patch.object(
                desktop_launcher, "identify_existing_service",
                side_effect=[None, "current"],
            ),
            patch.object(desktop_launcher, "port_in_use", return_value=False),
            patch.object(desktop_launcher.subprocess, "Popen", return_value=process) as popen,
            patch.object(desktop_launcher.webbrowser, "open_new_tab", return_value=True) as browser,
        ):
            result = desktop_launcher.start(
                self.root, self.config, wait_timeout=1, poll_interval=0
            )
        self.assertEqual(result, "started")
        popen.assert_called_once()
        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(Path(command[1]).resolve(), (self.root / "app.py").resolve())
        self.assertIn(str(self.data), command)
        self.assertEqual(options["cwd"], str(self.root))
        self.assertTrue(options["env"]["AIWORKSPACE_LAUNCHER_TOKEN"])
        self.assertTrue(options["env"]["AIWORKSPACE_LAUNCHER_STATE_DIR"])
        browser.assert_called_once()

    def test_start_timeout_terminates_only_the_child_it_created(self):
        process = Mock()
        process.poll.return_value = None
        with (
            patch.object(desktop_launcher, "identify_existing_service", return_value=None),
            patch.object(desktop_launcher, "port_in_use", return_value=False),
            patch.object(desktop_launcher.subprocess, "Popen", return_value=process),
            patch.object(desktop_launcher, "_terminate_started_process") as terminate,
        ):
            with self.assertRaises(desktop_launcher.LauncherError):
                desktop_launcher.start(
                    self.root, self.config, wait_timeout=0, poll_interval=0
                )
        terminate.assert_called_once_with(process)

    def test_health_endpoint_is_read_only(self):
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(self.data)
        )
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload, {"service": "AIWorkSpace", "status": "ok"})
        self.assertEqual(list((self.data / "events").iterdir()), [])

    def test_shutdown_requires_the_random_control_token(self):
        token = "correct-token-for-test"
        port = self.start_test_server(token)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("POST", "/api/local/shutdown", body=b"")
            response = connection.getresponse()
            response.read()
        finally:
            connection.close()
        self.assertEqual(response.status, 403)
        self.assertTrue(self.server_thread.is_alive())

    def test_shutdown_rejects_proxy_forwarded_requests_even_with_token(self):
        token = "correct-token-for-test"
        port = self.start_test_server(token)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request(
                "POST",
                "/api/local/shutdown",
                body=b"",
                headers={
                    "X-AIWorkSpace-Control-Token": token,
                    "X-Forwarded-Host": "example.tailnet.ts.net",
                },
            )
            response = connection.getresponse()
            response.read()
        finally:
            connection.close()
        self.assertEqual(response.status, 403)
        self.assertTrue(self.server_thread.is_alive())

    def test_stop_sends_the_matching_token_and_waits_for_service_exit(self):
        token = "matching-token-for-test"
        port = self.start_test_server(token)
        self.write_service_state(port, token)
        result = desktop_launcher.stop(wait_timeout=3, poll_interval=0.02)
        self.assertEqual(result, "stopped")
        self.server_thread.join(timeout=3)
        self.assertFalse(self.server_thread.is_alive())
        self.assertFalse((desktop_launcher.runtime_dir() / "service.json").exists())

    def test_stop_with_wrong_token_does_not_stop_service(self):
        port = self.start_test_server("server-token")
        self.write_service_state(port, "wrong-token")
        with self.assertRaises(desktop_launcher.LauncherError):
            desktop_launcher.stop(wait_timeout=0.2, poll_interval=0.02)
        self.assertTrue(self.server_thread.is_alive())

    def test_log_rotation_keeps_only_one_backup(self):
        path = desktop_launcher.log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (desktop_launcher.MAX_LOG_BYTES + 1))
        backup = path.with_name(path.name + ".1")
        backup.write_text("old backup", encoding="utf-8")
        desktop_launcher._rotate_log()
        self.assertFalse(path.exists())
        self.assertEqual(backup.stat().st_size, desktop_launcher.MAX_LOG_BYTES + 1)
        self.assertFalse(path.with_name(path.name + ".2").exists())

    def test_old_manually_started_service_is_never_stopped(self):
        with patch.object(
            desktop_launcher, "identify_existing_service", return_value="legacy"
        ):
            result = desktop_launcher.stop(self.config)
        self.assertEqual(result, "unmanaged")

    @unittest.skipUnless(sys.platform == "win32", "Windows Script Host syntax check")
    def test_vbs_scripts_parse_in_windows_script_host(self):
        repo = Path(__file__).resolve().parents[1]
        for name in (
            "start_aiworkspace.vbs",
            "stop_aiworkspace.vbs",
            "setup_desktop_shortcuts.vbs",
        ):
            result = subprocess.run(
                ["cscript.exe", "//nologo", str(repo / name), "--syntax-check"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_vbs_shortcuts_do_not_use_powershell_or_console_commands(self):
        repo = Path(__file__).resolve().parents[1]
        for name in (
            "start_aiworkspace.vbs",
            "stop_aiworkspace.vbs",
            "setup_desktop_shortcuts.vbs",
        ):
            content = (repo / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("powershell", content)
            self.assertNotIn("cmd.exe", content)
            self.assertTrue(content.isascii(), f"{name} must remain ASCII for Windows Script Host")
        start_script = (repo / "start_aiworkspace.vbs").read_text(encoding="utf-8")
        self.assertIn("shell.Run command, 0, False", start_script)
        setup_script = (repo / "setup_desktop_shortcuts.vbs").read_text(encoding="utf-8")
        self.assertIn("CreateShortcut", setup_script)
        self.assertIn("launcher.json", setup_script)


if __name__ == "__main__":
    unittest.main()
