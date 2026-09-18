"""After a paper, the owner's next chat turn must not inherit that session."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from conftest import ROOT, load_module

seal = load_module("seal_chat_session", "pt-shared/scripts/seal_chat_session.py")
plow_seal = load_module("plow_seal_session", "image/hermes/plow_seal_session.py")


class TestStamp:
    def test_request_writes_the_producing_session_key(self, tmp_path):
        stamp = tmp_path / "seal-session.json"
        seal.request(stamp, session_key="agent:main:plow_chat:dm:abc", platform="plow_chat")
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert data["session_key"] == "agent:main:plow_chat:dm:abc"
        assert data["platform"] == "plow_chat"
        assert data["pending"] is True
        assert data.get("delivered") is not True

    def test_peek_does_not_consume(self, tmp_path):
        stamp = tmp_path / "seal-session.json"
        seal.request(stamp, session_key="k", delivered=True)
        assert seal.peek(stamp)["delivered"] is True
        assert stamp.exists()
        assert seal.peek(stamp)["session_key"] == "k"


class TestEditionPostedSilences:
    def test_soon_stamp_does_not_swallow_a_real_reply(self, tmp_path):
        stamp = tmp_path / "seal.json"
        seal.request(stamp, session_key="k", delivered=False)
        assert plow_seal.edition_posted_this_turn(stamp) is False

    def test_after_the_pdf_any_recap_is_silence(self, tmp_path):
        stamp = tmp_path / "seal.json"
        seal.request(stamp, session_key="k", delivered=True)
        assert plow_seal.edition_posted_this_turn(stamp) is True

    def test_no_stamp_is_not_posted(self, tmp_path):
        assert plow_seal.edition_posted_this_turn(tmp_path / "nope.json") is False

    def test_consume_is_one_shot(self, tmp_path):
        stamp = tmp_path / "seal-session.json"
        seal.request(stamp, session_key="k")
        payload = seal.consume(stamp)
        assert payload["session_key"] == "k"
        assert stamp.exists() is False
        assert seal.consume(stamp) is None

    def test_missing_stamp_is_a_noop(self, tmp_path):
        assert seal.consume(tmp_path / "nope.json") is None


class TestKeysToSeal:
    def test_stamped_key_and_every_plow_chat_route(self):
        entries = [
            SimpleNamespace(
                session_key="agent:main:plow_chat:dm:home",
                platform=SimpleNamespace(value="plow_chat"),
            ),
            SimpleNamespace(
                session_key="cron:pt-daily-edition",
                platform=SimpleNamespace(value="cron"),
            ),
        ]
        keys = seal.keys_to_seal(
            {"session_key": "cron:pt-daily-edition", "platform": "cron"},
            entries,
        )
        assert "cron:pt-daily-edition" in keys
        assert "agent:main:plow_chat:dm:home" in keys
        assert len(keys) == 2


class TestAfterTurn:
    def test_no_stamp_does_not_touch_the_store(self, tmp_path):
        gateway = _FakeGateway()
        asyncio.run(plow_seal.maybe_seal_after_turn(gateway, stamp=tmp_path / "seal.json"))
        assert gateway.reset == []

    def test_stamp_resets_plow_chat_and_the_producing_session(self, tmp_path):
        stamp = tmp_path / "seal.json"
        seal.request(stamp, session_key="cron:job", platform="cron")
        gateway = _FakeGateway()
        gateway.session_store.entries = [
            SimpleNamespace(
                session_key="agent:main:plow_chat:dm:home",
                platform=SimpleNamespace(value="plow_chat"),
            ),
            SimpleNamespace(
                session_key="cron:job",
                platform=SimpleNamespace(value="cron"),
            ),
        ]
        asyncio.run(plow_seal.maybe_seal_after_turn(gateway, stamp=stamp))
        assert set(gateway.reset) == {"cron:job", "agent:main:plow_chat:dm:home"}
        assert stamp.exists() is False
        assert "agent:main:plow_chat:dm:home" in gateway.evicted


class TestPatcher:
    def test_rewrites_the_post_turn_hook(self):
        patcher = load_module("patch_seal_session", "image/hermes/patch_seal_session.py")
        src = (
            "    async def _hmwa_post_turn_hooks(self, hook_ctx, agent_result, response):\n"
            '        """agent:end hook, process-watcher scheduling, and watch-notification drain."""\n'
            '        await self.hooks.emit("agent:end", {\n'
        )
        out = patcher.apply(src)
        assert "maybe_seal_after_turn" in out
        assert out.count("await self.hooks.emit(\"agent:end\"") == 1

    def test_rewrites_the_silence_filter(self):
        patcher = load_module("patch_seal_session", "image/hermes/patch_seal_session.py")
        src = (
            "def is_intentional_silence_response(response: Any) -> bool:\n"
            '    """True only when ``response`` is exactly a silence marker.\n'
            "\n"
            "    Prose that merely mentions ``NO_REPLY`` must be delivered normally. A blank\n"
            "    response is not silence either — that is the empty-response failure path.\n"
            '    """\n'
            "    return any(c in LIVE_GATEWAY_SILENT_MARKERS for c in _canonical_silence_candidates(response))\n"
        )
        out = patcher.apply(src)
        assert "edition_posted_this_turn" in out

    def test_refuses_a_moved_marker(self):
        patcher = load_module("patch_seal_session", "image/hermes/patch_seal_session.py")
        try:
            patcher.apply("no hook here")
        except SystemExit as exc:
            assert "did not match" in str(exc)
        else:
            raise AssertionError("expected pin to refuse")


class _FakeAsyncStore:
    def __init__(self):
        self.entries = []
        self.reset_calls = []

    def list_sessions(self):
        return list(self.entries)

    async def reset_session(self, session_key):
        self.reset_calls.append(session_key)
        return SimpleNamespace(session_id="new")


class _FakeGateway:
    def __init__(self):
        store = _FakeAsyncStore()
        self.session_store = store
        self.async_session_store = store
        self.reset = store.reset_calls
        self.evicted = []
        self.cleared = []

    def _invalidate_session_run_generation(self, session_key, reason=""):
        return 1

    def _release_running_agent_state(self, session_key):
        return None

    def _evict_cached_agent(self, session_key):
        self.evicted.append(session_key)

    def _clear_conversation_scope(self, session_key, reason=""):
        self.cleared.append(session_key)

    def _cached_agent_for(self, session_key):
        return None
