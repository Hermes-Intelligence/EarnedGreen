#!/usr/bin/env python3
"""Tests for the `e2e` check kind: boot the app, drive it, tear it down.

These boot a REAL HTTP server on a real port and drive it over the network. The
kind is deliberately not coupled to Playwright -- `command` is whatever drives
the app -- so the whole thing is testable with no browser toolchain, which is
exactly why it can be tested at all.
"""
from __future__ import annotations

import socket
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import harness_checks

APP = '''\
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DISCOUNTED = {sentinel}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(str(DISCOUNTED).encode())

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", {port}), Handler).serve_forever()
'''

DRIVER = '''\
import sys
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:{port}/price") as response:
    body = response.read().decode()
assert body == "180", f"expected 180, got {{body}}"
'''


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class E2ECheck(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = Path(tempfile.mkdtemp(prefix="awbp-e2e-"))
        self.port = _free_port()
        (self.workspace / "driver.py").write_text(DRIVER.format(port=self.port), encoding="utf-8")

    def _write_app(self, sentinel: str) -> None:
        (self.workspace / "app.py").write_text(
            APP.format(port=self.port, sentinel=sentinel), encoding="utf-8")

    def _check(self, **overrides) -> dict:
        check = {
            "id": "price-is-discounted", "kind": "e2e", "authored_by": "harness",
            "start": [sys.executable, "app.py"],
            "ready_url": f"http://127.0.0.1:{self.port}/health",
            "command": [sys.executable, "driver.py"],
            "boot_timeout": 30,
        }
        check.update(overrides)
        return check

    def _run(self, check: dict) -> dict:
        suite = {"schema_version": 1, "config": {}, "checks": [check]}
        return harness_checks.run_suite(suite, self.workspace)["checks"][0]

    def test_green_when_the_app_behaves(self) -> None:
        self._write_app("180")
        self.assertEqual(self._run(self._check())["verdict"], "PASS")

    def test_red_when_the_app_misbehaves(self) -> None:
        """The check must fail on behaviour, not merely on the app being up."""
        self._write_app("999")
        row = self._run(self._check())
        self.assertEqual(row["verdict"], "FAIL")
        self.assertIn("did not behave as required", row["failures"][0]["reason"])

    def test_app_that_never_becomes_ready_is_a_clear_failure(self) -> None:
        (self.workspace / "app.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
        row = self._run(self._check(boot_timeout=10))
        self.assertEqual(row["verdict"], "FAIL")
        self.assertIn("exited with 7", row["failures"][0]["reason"])

    def test_missing_ready_url_is_rejected(self) -> None:
        """A fixed sleep instead of a readiness probe is a flake generator."""
        self._write_app("180")
        row = self._run(self._check(ready_url=None))
        self.assertEqual(row["verdict"], "FAIL")
        self.assertIn("ready_url", row["failures"][0]["reason"])

    def test_unstartable_app_does_not_raise(self) -> None:
        row = self._run(self._check(start=["definitely-not-a-real-binary-xyz"]))
        self.assertEqual(row["verdict"], "FAIL")
        self.assertIn("could not be started", row["failures"][0]["reason"])

    def test_app_is_torn_down_even_when_the_driver_fails(self) -> None:
        """A leaked server poisons every later check with a port conflict, and
        the failure then looks like the agent's fault."""
        self._write_app("180")
        (self.workspace / "driver.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
        self.assertEqual(self._run(self._check())["verdict"], "FAIL")
        with socket.socket() as sock:
            sock.settimeout(2)
            self.assertNotEqual(sock.connect_ex(("127.0.0.1", self.port)), 0,
                                "the app is still listening: it was not torn down")


if __name__ == "__main__":
    unittest.main(verbosity=2)
