"""plow-init recopies seed display; overlay must win over loud plow_chat defaults."""
import pytest
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


SEED = "model:\n  default: anthropic/claude-sonnet-5\ncontext_file_max_chars: 40000\n"
HOME = "model:\n  default: anthropic/claude-sonnet-5\ndisplay:\n  tool_progress: 'off'\n_config_version: 37\n"
CAP = "context_file_max_chars: {}\n"


@pytest.mark.parametrize(
    "home, want",
    [(HOME, HOME + CAP.format(40000)), (CAP.format(20000) + HOME, CAP.format(40000) + HOME)],
    ids=["absent", "lower"],
)
def test_boot_carries_the_context_cap_into_an_existing_home(tmp_path, home, want):
    (tmp_path / "seed.yaml").write_text(SEED)
    config = tmp_path / "config.yaml"
    config.write_text(home)
    args = ["--home", str(config), str(tmp_path / "seed.yaml")]
    merge.main(args)
    assert config.read_text() == want
    before = config.stat()
    merge.main(args)
    assert (config.stat().st_ino, config.stat().st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


@pytest.mark.parametrize("seed, error", [(None, FileNotFoundError), ("model: {}\n", SystemExit)], ids=["missing", "no-cap"])
def test_home_merge_fails_loudly_without_a_seed_cap(tmp_path, seed, error):
    if seed:
        (tmp_path / "seed.yaml").write_text(seed)
    (tmp_path / "config.yaml").write_text(HOME)
    with pytest.raises(error, match=str(tmp_path / "seed.yaml")):
        merge.main(["--home", str(tmp_path / "config.yaml"), str(tmp_path / "seed.yaml")])
    assert (tmp_path / "config.yaml").read_text() == HOME
