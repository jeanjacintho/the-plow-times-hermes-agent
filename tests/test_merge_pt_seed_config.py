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


def test_overlay_copies_context_file_max_chars_onto_the_seed():
    seed = {"display": {}}
    ours = {"display": {}, "context_file_max_chars": 40000}
    out = merge.overlay_context_file_max_chars(seed, ours)
    assert out["context_file_max_chars"] == 40000


def test_overlay_refuses_a_missing_context_file_max_chars():
    try:
        merge.overlay_context_file_max_chars({"display": {}}, {"display": {}})
    except SystemExit as exc:
        assert "context_file_max_chars" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
