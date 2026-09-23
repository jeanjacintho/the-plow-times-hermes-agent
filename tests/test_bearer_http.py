"""bearer_http.py -- get_json, the GET counterpart to post_json_read (issue #85:
chat_message_id.py reads a message uid back through it)."""
from __future__ import annotations

import urllib.error

import pytest

from conftest import load_module

bearer = load_module("bearer_http", "pt-shared/scripts/bearer_http.py")


class _Response:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestGetJson:
    def test_a_successful_get_returns_the_parsed_body(self, monkeypatch):
        seen = {}

        def fake_open(request, *, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["headers"] = dict(request.header_items())
            return _Response(b'{"messages": [{"uid": "msg_1"}]}')

        monkeypatch.setattr(bearer, "open_no_redirect", fake_open)
        result = bearer.get_json("https://api.example", "/v1/chats/cht_1/messages", "tok", "Plow Chat")
        assert result == {"messages": [{"uid": "msg_1"}]}
        assert seen["url"] == "https://api.example/v1/chats/cht_1/messages"
        assert seen["method"] == "GET"
        assert seen["headers"]["Authorization"] == "Bearer tok"

    def test_an_http_error_exits_by_label(self, monkeypatch):
        def fake_open(request, *, timeout):
            raise urllib.error.HTTPError(request.full_url, 500, "Internal Server Error", {}, None)

        monkeypatch.setattr(bearer, "open_no_redirect", fake_open)
        with pytest.raises(SystemExit, match="Plow Chat returned HTTP 500"):
            bearer.get_json("https://api.example", "/v1/chats/cht_1/messages", "tok", "Plow Chat")

    def test_a_url_error_exits_by_label(self, monkeypatch):
        def fake_open(request, *, timeout):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(bearer, "open_no_redirect", fake_open)
        with pytest.raises(SystemExit, match="GET Plow Chat failed"):
            bearer.get_json("https://api.example", "/v1/chats/cht_1/messages", "tok", "Plow Chat")

    def test_a_non_json_body_exits_by_label(self, monkeypatch):
        monkeypatch.setattr(bearer, "open_no_redirect", lambda request, *, timeout: _Response(b"not json"))
        with pytest.raises(SystemExit, match="non-JSON response"):
            bearer.get_json("https://api.example", "/v1/chats/cht_1/messages", "tok", "Plow Chat")
