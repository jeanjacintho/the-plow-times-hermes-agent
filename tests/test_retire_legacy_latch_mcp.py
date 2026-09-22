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


def _body():
    """The python the hook pipes to the interpreter, run here on this pytest's own."""
    text = HOOK.read_text()
    return text.split("<<'PY'\n", 1)[1].rsplit("PY\n", 1)[0]


def _run(tmp_path, config):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    subprocess.run([sys.executable, "-c", _body(), str(path)], check=True)
    return yaml.safe_load(path.read_text())


def test_the_legacy_entry_goes_and_the_image_managed_one_stays(tmp_path):
    out = _run(tmp_path, {
        "mcp_servers": {
            "latch": {"url": "https://api.plow.co/v1/relay/devices/${DOMO_DEVICE_UID}/mcp", "enabled": True},
            "plow": {"url": "${PLOW_MCP_URL}", "enabled": True},
        },
        "cron": {"wrap_response": False},
    })

    assert out["mcp_servers"] == {"plow": {"url": "${PLOW_MCP_URL}", "enabled": True}}
    # Everything the hook does not recognise is left exactly as it found it.
    assert out["cron"] == {"wrap_response": False}


def test_the_key_itself_goes_when_latch_was_the_only_entry(tmp_path):
    # An empty mapping reads as "this agent declares no relay" and would clobber
    # the image-managed entry on merge, which is the failure this PR is about.
    out = _run(tmp_path, {"mcp_servers": {"latch": {"url": "x", "enabled": True}}, "agent": {"api_max_retries": 9}})

    assert "mcp_servers" not in out
    assert out["agent"] == {"api_max_retries": 9}


@pytest.mark.parametrize("config", [
    {"mcp_servers": {"plow": {"url": "${PLOW_MCP_URL}"}}},
    {"cron": {"wrap_response": False}},
])
def test_a_config_with_no_legacy_entry_is_untouched(tmp_path, config):
    assert _run(tmp_path, config) == config
