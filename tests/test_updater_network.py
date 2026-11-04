"""Fault injection for updater transport; no public network or real data."""
import base64
import http.client
import json
import socket
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import updater
from test_updater import FakeResponse, COMMIT


class NetworkTests(unittest.TestCase):
    def test_transient_failures_recover_in_same_check(self):
        for error in (TimeoutError(), URLError(socket.gaierror()),
                      ConnectionResetError(), http.client.IncompleteRead(b"partial")):
            with self.subTest(error=type(error).__name__), patch.object(
                    updater, "urlopen", side_effect=[error, FakeResponse(b"ok")]) as request, patch.object(
                    updater.time, "sleep") as delay:
                self.assertEqual(updater._read_url(updater.API_COMMIT_URL, 100), b"ok")
                self.assertEqual(request.call_count, 2)
                delay.assert_called_once_with(0.5)

    def test_retry_limit_and_diagnostic(self):
        with patch.object(updater, "urlopen", side_effect=TimeoutError()) as request, patch.object(
                updater.time, "sleep"):
            with self.assertRaisesRegex(updater.UpdateError, "超时"):
                updater._read_url(updater.API_COMMIT_URL, 100)
            self.assertEqual(request.call_count, 3)

    def test_permanent_failures_are_not_retried(self):
        for error, message in ((URLError(ssl.SSLCertVerificationError()), "证书"),
                (HTTPError(updater.API_COMMIT_URL, 429, "limit", {}, None), "限流"),
                (HTTPError(updater.API_COMMIT_URL, 403, "limit",
                           {"X-RateLimit-Remaining": "0"}, None), "限流"),
                (HTTPError(updater.API_COMMIT_URL, 407, "proxy", {}, None), "代理"),
                (HTTPError(updater.API_COMMIT_URL, 404, "missing", {}, None), "404")):
            with self.subTest(message=message), patch.object(updater, "urlopen", side_effect=error) as request:
                with self.assertRaisesRegex(updater.UpdateError, message):
                    updater._read_url(updater.API_COMMIT_URL, 100)
                self.assertEqual(request.call_count, 1)

    def test_server_failure_can_recover(self):
        with patch.object(updater, "urlopen", side_effect=[
                HTTPError(updater.API_COMMIT_URL, 503, "busy", {}, None), FakeResponse(b"ok")]), patch.object(
                updater.time, "sleep"):
            self.assertEqual(updater._read_url(updater.API_COMMIT_URL, 100), b"ok")

    def test_version_fallback_is_official_and_pinned(self):
        body = json.dumps({"path": "VERSION", "type": "file", "encoding": "base64",
                           "content": base64.b64encode(b"2.0.6\n").decode()}).encode()
        with patch.object(updater, "urlopen", side_effect=[TimeoutError()] * 3 + [FakeResponse(body)]) as request, patch.object(
                updater.time, "sleep"):
            self.assertEqual(updater._read_remote_version(COMMIT), b"2.0.6\n")
            self.assertEqual(request.call_args.args[0].full_url,
                f"https://api.github.com/repos/{updater.REPOSITORY}/contents/VERSION?ref={COMMIT}")

    def test_security_failure_does_not_fallback_or_retry(self):
        with patch.object(updater, "urlopen", return_value=FakeResponse(b"bad", "https://evil.invalid/")) as request:
            with self.assertRaises(updater.UpdateError):
                updater._read_remote_version(COMMIT)
            self.assertEqual(request.call_count, 1)

    def test_malformed_fallback_fails_closed(self):
        with patch.object(updater, "urlopen", side_effect=[TimeoutError()] * 3 + [FakeResponse(b"{}")]), patch.object(
                updater.time, "sleep"):
            with self.assertRaisesRegex(updater.UpdateError, "版本文件"):
                updater._read_remote_version(COMMIT)

    def test_untrusted_initial_url_is_never_requested(self):
        with patch.object(updater, "urlopen") as request:
            with self.assertRaises(updater.UpdateError):
                updater._read_url("https://evil.invalid/", 100)
            request.assert_not_called()
