"""convert_delivery.py — owner local hour to container cron hour."""
from __future__ import annotations

import pytest

from conftest import load_module

conv = load_module("convert_delivery", "pt-setup/scripts/convert_delivery.py")


class TestConvert:
    def test_sao_paulo_morning_to_utc(self):
        # Brazil has no DST in 2026: 07:00 -03 == 10:00 UTC, year-round.
        assert conv.convert("07:00", "America/Sao_Paulo", "UTC") == "10:00"

    def test_same_zone_is_unchanged(self):
        assert conv.convert("07:00", "America/Sao_Paulo", "America/Sao_Paulo") == "07:00"

    def test_malformed_hour_refused(self):
        with pytest.raises(SystemExit, match="strict HH:MM"):
            conv.convert("7:00", "America/Sao_Paulo", "UTC")

    def test_unknown_owner_tz_refused(self):
        with pytest.raises(SystemExit, match="unknown owner timezone"):
            conv.convert("07:00", "Not/AZone", "UTC")

    def test_cli_prints_converted_hour(self, monkeypatch, capsys):
        monkeypatch.setenv("TZ", "UTC")
        conv.main(["--local-hour", "07:00", "--owner-tz", "America/Sao_Paulo"])
        assert capsys.readouterr().out.strip() == "10:00"

    def test_cli_empty_container_tz_refused(self, monkeypatch):
        monkeypatch.delenv("TZ", raising=False)
        with pytest.raises(SystemExit, match="container TZ is empty"):
            conv.main(["--local-hour", "07:00", "--owner-tz", "UTC"])
