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

from bearer_http import get_json, open_no_redirect, require

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
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                return obj
        raise LatchError("empty latch stream")
    obj = json.loads(text) if text.strip() else {}
    if not isinstance(obj, dict) or ("result" not in obj and "error" not in obj):
        raise LatchError("latch returned no result")
    return obj


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
            # A blocked run names what the owner must do to unblock it.
            action = (parsed.get("diagnosis") or {}).get("owner_action")
            raise LatchError(f"latch {status}" + (f": {action}" if action else ""))
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


def finish_command(call_tool, result, step):
    """A plow_run_command result that has exited: polls a still-running job's
    handle through plow_get_output, then refuses anything without an exit_code.

    A network-enabled job outlives Latch's wait_ms and keeps running, so a
    'running' reply is not a failure yet. If the job never finishes inside
    POLL_SECONDS, or polling it fails or is blocked, the print may still
    happen: the error says the outcome is unknown, with the owner's action
    when Latch names one.
    """
    for _ in range(POLL_SECONDS):
        if not isinstance(result, dict):
            break
        # A blocked or parked run names what the owner must do, whether it is
        # still running or came back terminal (with or without an exit_code).
        action = (result.get("diagnosis") or {}).get("owner_action")
        if action:
            raise LatchError(f"{step} outcome unknown: {action}")
        handle = result.get("handle")
        if "exit_code" in result or result.get("status") != "running" or not handle:
            break
        time.sleep(1)
        try:
            result = call_tool("plow_get_output", {"handle": handle})
        except LatchError as exc:
            raise LatchError(f"{step} outcome unknown: {exc}") from exc
    if not isinstance(result, dict) or "exit_code" not in result:
        raise LatchError(f"{step} outcome unknown: still running")
    return result


class LatchClient:
    """One stateless MCP call against the owner's Latch device.

    Latch's MCP server is stateless (each request is a fresh instance, no
    session held), and the plugin's own production relay call sends a bare
    tools/call with no initialize -- so this does too.
    """

    def __init__(self, url, token):
        self.url = url
        self.token = token

    @classmethod
    def for_device(cls, base, device, token):
        """A static DOMO_* pair names its device; build that device's URL."""
        return cls(f"{base.rstrip('/')}/v1/relay/devices/{device}/mcp", token)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _call(self, name, arguments):
        data = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url, method="POST", data=data, headers=self._headers(),
        )
        try:
            with open_no_redirect(request, timeout=MCP_TIMEOUT) as response:
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise LatchError(f"latch HTTP {exc.code} {exc.reason}")
        except urllib.error.URLError:
            raise LatchError("Mac unreachable")
        msg = decode_mcp_body(ctype, raw)
        if "error" in msg:
            err = msg["error"]
            detail = err.get("message", err) if isinstance(err, dict) else err
            raise LatchError(f"latch {detail}")
        return unwrap_tool_result(msg.get("result") or {})

    def call_tool(self, name, arguments):
        """One tool call, settled: a pending handle is polled to a result."""
        return settle(
            self._call(name, arguments),
            lambda handle: self._call("plow_get_result", {"handle": handle}),
        )


def hosted_mcp_url(base, agent_token):
    """This agent's own relay MCP URL, from the identity endpoint it boots on.

    `GET /v1/agents/me` returns `mcp_url` gated on the credential's
    `relay:call` scope -- which every hosted agent's credential carries --
    and NOT on a paired Mac: the relay answers 404 until one connects. So a
    URL here means "entitled to call the relay", not "the Mac is up". Use the
    value verbatim: an agent reaching Plow through a proxy is handed a
    proxied URL, which rebuilding the path from `base` would discard.

    None only when the credential lacks the scope.
    """
    identity = get_json(base, "/v1/agents/me", agent_token, "Plow agent identity")
    url = identity.get("mcp_url") if isinstance(identity, dict) else None
    return url.strip() if isinstance(url, str) and url.strip() else None


def connect():
    """A session with the owner's Mac, by whichever credential this install has.

    A self-hosted install pastes a static DOMO_* pair into the home's .env
    (README, "create a static credential"). A Plow-hosted install has no such
    step and never gets one -- but its own agent credential already carries
    the `relay:call` scope the relay MCP endpoint requires, so the URL is
    derived rather than demanded. Before this, a hosted install could not
    print at all: `require` refused on DOMO_DEVICE_UID every run.
    """
    base = os.environ.get("PLOW_API_BASE", "https://api.plow.co").strip() or "https://api.plow.co"
    device = os.environ.get("DOMO_DEVICE_UID", "").strip()
    token = os.environ.get("DOMO_MCP_TOKEN", "").strip()
    if device and token:
        return LatchClient.for_device(base, device, token)
    agent_token = require("PLOW_AGENT_TOKEN")
    url = hosted_mcp_url(base, agent_token)
    if not url:
        raise LatchError(
            "this agent's credential cannot call the relay (no relay:call scope)"
        )
    return LatchClient(url, agent_token)
