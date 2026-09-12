"""setup_needed.py — first-run gate for live chat."""
from __future__ import annotations

import json

from conftest import load_module

needed = load_module("setup_needed", "pt-shared/scripts/setup_needed.py")

VALID = {
    "owner": {"timezone": "America/Sao_Paulo"},
    "delivery": {"hour": "07:00"},
    "printer": {"configured": False, "name": None},
}


class TestSetupNeeded:
    def test_missing_file_is_needed(self, tmp_path):
        assert needed.setup_needed(tmp_path / "absent.json") is True

    def test_garbage_is_needed(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("nope")
        assert needed.setup_needed(path) is True

    def test_valid_is_ready(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(VALID))
        assert needed.setup_needed(path) is False

    def test_missing_timezone_is_needed(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({**VALID, "owner": {}}))
        assert needed.setup_needed(path) is True

    def test_printer_false_is_ready(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(VALID))
        assert needed.setup_needed(path) is False

    def test_cli_prints_setup_needed(self, tmp_path, capsys):
        needed.main(["setup_needed.py", str(tmp_path / "missing.json")])
        assert capsys.readouterr().out.strip() == "SETUP_NEEDED"

    def test_cli_prints_ready(self, tmp_path, capsys):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(VALID))
        needed.main(["setup_needed.py", str(path)])
        assert capsys.readouterr().out.strip() == "READY"
