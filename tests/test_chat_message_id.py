"""chat_message_id.py -- issue #85's item for a plow_chat message with no
Messages or mail counterpart: the owner's own latest message uid, read back
through the same Plow Chat API post_to_chat.py already posts through."""
from __future__ import annotations

import contextlib
import io

import pytest

from conftest import load_module

cmi = load_module("chat_message_id", "pt-shared/scripts/chat_message_id.py")


def out():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cmi.main()
    return code, buf.getvalue().strip()


class TestMessagesFrom:
    def test_a_bare_list_is_used_as_is(self):
        assert cmi._messages_from([{"uid": "msg_1"}]) == [{"uid": "msg_1"}]

    @pytest.mark.parametrize("key", ["messages", "data", "items"])
    def test_a_wrapped_list_is_unwrapped(self, key):
        assert cmi._messages_from({key: [{"uid": "msg_1"}]}) == [{"uid": "msg_1"}]

    @pytest.mark.parametrize("payload", [
        {"other": [{"uid": "msg_1"}]},  # unrecognized key
        {"messages": "not-a-list"},
        None,
        "garbage",
        42,
    ])
    def test_an_unrecognized_shape_yields_nothing(self, payload):
        assert cmi._messages_from(payload) == []


class TestLatestMessageUid:
    def test_the_last_entrys_uid_wins(self):
        messages = [{"uid": "msg_1"}, {"uid": "msg_2"}]
        assert cmi.latest_message_uid(messages) == "msg_2"

    def test_an_empty_list_has_no_handle(self):
        assert cmi.latest_message_uid([]) is None

    def test_a_last_entry_that_is_not_a_dict_has_no_handle(self):
        assert cmi.latest_message_uid([{"uid": "msg_1"}, "not-a-dict"]) is None

    @pytest.mark.parametrize("last", [
        {},  # no uid key at all
        {"uid": ""},  # blank
        {"uid": "   "},  # blank once stripped
        {"uid": 123},  # not a string
        {"uid": None},
    ])
    def test_a_last_entry_with_no_usable_uid_has_no_handle(self, last):
        assert cmi.latest_message_uid([last]) is None


class TestResolveHandle:
    def test_the_channels_latest_uid_is_the_handle(self, monkeypatch):
        monkeypatch.setattr(cmi, "resolve_chat", lambda: ("https://api.example", "cht_1", "tok"))
        monkeypatch.setattr(
            cmi, "get_json",
            lambda base, path, token, label: {"messages": [{"uid": "msg_1"}, {"uid": "msg_2"}]},
        )
        assert cmi.resolve_handle() == "msg_2"

    def test_env_not_set_yields_no_handle(self, monkeypatch):
        def refuse():
            raise SystemExit("error: PLOW_API_BASE is not set")

        monkeypatch.setattr(cmi, "resolve_chat", refuse)
        assert cmi.resolve_handle() is None

    def test_a_failed_get_yields_no_handle(self, monkeypatch):
        monkeypatch.setattr(cmi, "resolve_chat", lambda: ("https://api.example", "cht_1", "tok"))

        def fail(*a, **k):
            raise SystemExit("error: Plow Chat returned HTTP 500 Internal Server Error")

        monkeypatch.setattr(cmi, "get_json", fail)
        assert cmi.resolve_handle() is None

    def test_an_empty_channel_yields_no_handle(self, monkeypatch):
        monkeypatch.setattr(cmi, "resolve_chat", lambda: ("https://api.example", "cht_1", "tok"))
        monkeypatch.setattr(cmi, "get_json", lambda *a, **k: {"messages": []})
        assert cmi.resolve_handle() is None


class TestMain:
    def test_prints_the_handle_line(self, monkeypatch):
        monkeypatch.setattr(cmi, "resolve_handle", lambda: "msg_9f2a")
        assert out() == (0, "HANDLE:msg_9f2a")

    def test_prints_none_when_no_handle_is_available(self, monkeypatch):
        monkeypatch.setattr(cmi, "resolve_handle", lambda: None)
        assert out() == (0, "HANDLE:none")
