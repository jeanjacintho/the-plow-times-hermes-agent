#!/usr/bin/env python3
"""latch_mcp.py -- one MCP session with the owner's Mac through Latch's relay.

The print leg and the wiki both reach the Mac through this client, so a relay
quirk is fixed in one place. A failure raises LatchError with the reason;
each caller says what did not happen ("page not printed", "edition not
recorded").
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from bearer_http import NoRedirect, require

MCP_TIMEOUT = 60
POLL_SECONDS = 120


class LatchError(Exception):
    """The Mac did not do what was asked; str() says why."""


def decode_mcp_body(content_type, raw):
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    ctype = content_type or ""
    if "text/event-stream" in ctype:
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if not chunk or chunk == "[DONE]":
                continue
            obj = json.loads(chunk)
            if "result" in obj or "error" in obj:
                return obj
        raise LatchError("empty latch stream")
    if not text.strip():
        return {}
    return json.loads(text)


def unwrap_tool_result(result):
    if not isinstance(result, dict):
        return {"raw": result}
    texts = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(item.get("text") or "")
    blob = "\n".join(texts).strip()
    if result.get("isError"):
        raise LatchError(blob or str(result))
    if blob:
        try:
            return json.loads(blob)
        except ValueError:
            return {"raw": blob}
    return result


def settle(parsed, get_result, sleep=time.sleep, max_wait=POLL_SECONDS):
    if not isinstance(parsed, dict):
        return parsed
    for _ in range(max_wait + 1):
        status = parsed.get("status")
        if status == "pending":
            handle = parsed.get("handle")
            if not handle:
                raise LatchError("latch pending with no handle")
            sleep(1)
            parsed = get_result(handle)
            continue
        if status in ("denied", "failed", "expired", "unknown", "blocked"):
            raise LatchError(f"latch {status}")
        if status == "ready":
            inner = parsed.get("result", parsed)
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except ValueError:
                    inner = {"raw": inner}
            return inner
        return parsed
    raise LatchError("latch timed out")


class LatchClient:
    """One Streamable-HTTP MCP session against the owner's Latch device."""

    def __init__(self, base, device, token, name):
        self.url = f"{base.rstrip('/')}/v1/relay/devices/{device}/mcp"
        self.token = token
        self.name = name
        self.session_id = None
        self._id = 0
        self._initialize()

    def _headers(self):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url, method="POST", data=data, headers=self._headers(),
        )
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(request, timeout=MCP_TIMEOUT) as response:
                sid = response.headers.get("Mcp-Session-Id") or response.headers.get(
                    "mcp-session-id"
                )
                if sid:
                    self.session_id = sid
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise LatchError(f"latch HTTP {exc.code} {exc.reason}")
        except urllib.error.URLError as exc:
            raise LatchError("Mac unreachable; next scheduled run retries")
        return decode_mcp_body(ctype, raw)

    def _initialize(self):
        self._id += 1
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": self.name, "version": "1"},
                },
            }
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(self, name, arguments):
        self._id += 1
        msg = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in msg:
            err = msg["error"]
            detail = err.get("message", err) if isinstance(err, dict) else err
            raise LatchError(f"latch {detail}")
        return unwrap_tool_result(msg.get("result") or {})


def connect(name):
    """A session as this agent's static Latch credential (DOMO_* in the home's .env)."""
    base = os.environ.get("PLOW_API_BASE", "https://api.plow.co").strip() or "https://api.plow.co"
    return LatchClient(base, require("DOMO_DEVICE_UID"), require("DOMO_MCP_TOKEN"), name)
