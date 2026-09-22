"""The one-time migration that drops this repo's retired `latch` mcp_servers entry.

The image's config.yaml lands inside the agent-home volume, so an existing
install never sees the deletion from runtime/config.yaml; plow-init preserves
every mcp_servers entry but its own. Without this hook the legacy entry sits
there enabled, still interpolating the retired DOMO_* pair.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

HOOK = pathlib.Path(__file__).resolve().parents[1] / "image" / "cont-init.d" / "03-retire-legacy-latch-mcp"

LEGACY = {
    "url": "https://api.plow.co/v1/relay/devices/${DOMO_DEVICE_UID}/mcp",
    "headers": {"Authorization": "Bearer ${DOMO_MCP_TOKEN}"},
    "enabled": True,
}


def _body():
    """The python the hook pipes to the interpreter, run here on this pytest's own."""
    text = HOOK.read_text()
    return text.split("<<'PY'\n", 1)[1].rsplit("PY\n", 1)[0]


def _run(tmp_path, config=None, *, raw=None):
    path = tmp_path / "config.yaml"
    marker = tmp_path / "marker"
    if raw is not None:
        path.write_text(raw)
    elif config is not None:
        path.write_text(yaml.safe_dump(config, sort_keys=False))
    subprocess.run([sys.executable, "-c", _body(), str(path), str(marker)], check=True)
    return yaml.safe_load(path.read_text()) if path.exists() else None


def test_the_legacy_entry_goes_and_the_image_managed_one_stays(tmp_path):
    out = _run(tmp_path, {
        "mcp_servers": {"latch": LEGACY, "plow": {"url": "${PLOW_MCP_URL}", "enabled": True}},
        "cron": {"wrap_response": False},
    })

    assert out["mcp_servers"] == {"plow": {"url": "${PLOW_MCP_URL}", "enabled": True}}
    # Everything the hook does not recognise is left exactly as it found it.
    assert out["cron"] == {"wrap_response": False}


def test_the_key_itself_goes_when_latch_was_the_only_entry(tmp_path):
    # An empty mapping reads as "this agent declares no relay" and would clobber
    # the image-managed entry on merge, which is the failure this PR is about.
    out = _run(tmp_path, {"mcp_servers": {"latch": LEGACY}, "agent": {"api_max_retries": 9}})

    assert "mcp_servers" not in out
    assert out["agent"] == {"api_max_retries": 9}


def test_the_entry_is_found_whatever_shape_the_yaml_is_in(tmp_path):
    # A `grep '^  latch:'` gate used to guard the parser, and it only matched
    # one serialization. The install whose config is in flow style is still an
    # install carrying the legacy entry.
    out = _run(tmp_path, raw='mcp_servers: {latch: {url: "x"}, plow: {url: "${PLOW_MCP_URL}"}}\n')

    assert out == {"mcp_servers": {"plow": {"url": "${PLOW_MCP_URL}"}}}


def test_it_runs_once_so_a_later_latch_server_survives(tmp_path):
    # The whole reason no predicate guards the delete: after the migration has
    # run, a server that happens to be called `latch` is simply not its
    # business. Re-running must be a no-op even on an entry it would have eaten.
    _run(tmp_path, {"mcp_servers": {"latch": LEGACY, "plow": {"url": "${PLOW_MCP_URL}"}}})

    later = {"mcp_servers": {"latch": {"url": "https://latch.example/mcp"}}}
    assert _run(tmp_path, later) == later


def test_a_home_that_never_carried_the_entry_is_still_marked(tmp_path):
    # Otherwise the hook parses config.yaml on every boot forever, which is the
    # standing-reconcile shape this is deliberately not.
    _run(tmp_path, {"mcp_servers": {"plow": {"url": "${PLOW_MCP_URL}"}}})

    assert (tmp_path / "marker").exists()


def test_the_config_keeps_its_mode_and_owner(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({"mcp_servers": {"latch": LEGACY, "plow": {"url": "x"}}}, sort_keys=False))
    path.chmod(0o644)
    before = path.stat()

    subprocess.run([sys.executable, "-c", _body(), str(path), str(tmp_path / "marker")], check=True)

    after = path.stat()
    assert after.st_mode == before.st_mode
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)
    assert not (tmp_path / "config.yaml.tmp").exists()


@pytest.mark.parametrize("config", [
    {"mcp_servers": {"plow": {"url": "${PLOW_MCP_URL}"}}},
    {"cron": {"wrap_response": False}},
])
def test_a_config_with_no_legacy_entry_is_untouched(tmp_path, config):
    assert _run(tmp_path, config) == config


def test_an_absent_config_is_not_created(tmp_path):
    assert _run(tmp_path) is None
