"""plow-init recopies seed display; overlay must win over loud plow_chat defaults."""
from conftest import load_module

merge = load_module("pt_merge_seed", "image/merge_pt_seed_config.py")


def test_overlay_turns_off_interim_and_long_running_without_dropping_seed_keys():
    seed = {
        "display": {
            "memory_notifications": "on",
            "busy_ack_enabled": False,
            "platforms": {
                "plow_chat": {
                    "tool_progress": "off",
                    "long_running_notifications": True,
                }
            },
        }
    }
    ours = {
        "display": {
            "tool_progress": "off",
            "interim_assistant_messages": False,
            "long_running_notifications": False,
            "busy_ack_detail": False,
            "live_status": "off",
            "platforms": {
                "plow_chat": {
                    "tool_progress": "off",
                    "interim_assistant_messages": False,
                    "long_running_notifications": False,
                    "busy_ack_detail": False,
                    "live_status": "off",
                }
            },
        }
    }
    out = merge.overlay_display(seed, ours)
    disp = out["display"]
    pc = disp["platforms"]["plow_chat"]
    assert disp["memory_notifications"] == "on"
    assert disp["busy_ack_enabled"] is False
    assert disp["interim_assistant_messages"] is False
    assert disp["long_running_notifications"] is False
    assert disp["tool_progress"] == "off"
    assert pc["interim_assistant_messages"] is False
    assert pc["long_running_notifications"] is False
    assert pc["tool_progress"] == "off"


def test_yaml11_bare_off_becomes_the_string_hermes_reads():
    out = merge.overlay_display(
        {"display": {}},
        {
            "display": {
                "tool_progress": False,
                "live_status": False,
                "interim_assistant_messages": False,
                "long_running_notifications": False,
                "platforms": {
                    "plow_chat": {
                        "tool_progress": False,
                        "live_status": False,
                        "interim_assistant_messages": False,
                        "long_running_notifications": False,
                    }
                },
            }
        },
    )
    disp = out["display"]
    pc = disp["platforms"]["plow_chat"]
    assert disp["tool_progress"] == "off"
    assert disp["live_status"] == "off"
    assert pc["tool_progress"] == "off"
    assert pc["live_status"] == "off"


def test_overlay_model_replaces_fleet_glm_default_with_sonnet():
    # Base ef00193 pins z-ai/glm-5.2 on plow-seed; plow-init recopies that
    # onto home every boot. The newspaper stays on Sonnet 5 by stamping
    # runtime/config.yaml's model onto the seed -- not by compose env.
    seed = {
        "model": {"default": "z-ai/glm-5.2", "provider": "plow"},
        "providers": {
            "plow": {
                "models": {
                    "z-ai/glm-5.2": {},
                    "anthropic/claude-sonnet-5": {},
                }
            }
        },
    }
    ours = {
        "model": {"default": "anthropic/claude-sonnet-5", "provider": "plow"},
        "providers": {
            "plow": {
                "models": {"anthropic/claude-sonnet-5": {}},
            }
        },
    }
    out = merge.overlay_model(seed, ours)
    assert out["model"]["default"] == "anthropic/claude-sonnet-5"
    assert out["model"]["provider"] == "plow"
    models = out["providers"]["plow"]["models"]
    assert "anthropic/claude-sonnet-5" in models
    assert out["model"]["default"] != "z-ai/glm-5.2"
