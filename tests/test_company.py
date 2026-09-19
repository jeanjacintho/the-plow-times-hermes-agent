import json
import os
import subprocess

import pytest

from conftest import load_module

company = load_module("company", "pt-priority/scripts/company.py")

PAPER = "2026-09-01T07:12-07:00"


def record(as_of):
    return json.dumps({"facts": {"revenue": {"value": "$4K MRR", "source": "owner", "as_of": as_of}}})


def revenue(value, as_of):
    return {"key": "revenue", "value": value, "source": "mail sent by the owner", "as_of": as_of}


def shown(value, as_of):
    return f"revenue: {value} (as of {as_of}; source: mail sent by the owner)"


STORED = record(PAPER)
SHOWN = f"revenue: $4K MRR (as of {PAPER}; source: owner)"
REFUSED = f"REFUSED: revenue is already recorded as of {PAPER}"


# fact None runs `show`; otherwise the fact is written to a request file and `set` reads it.
@pytest.mark.parametrize("stored, fact, printed, shown", [
    (None, None, "EMPTY", "EMPTY"),
    # A correction later the same day as the paper wins.
    (STORED, revenue("$5K MRR", "2026-09-01T09:30-07:00"), "SET: revenue",
     shown("$5K MRR", "2026-09-01T09:30-07:00")),
    # Newer evidence of the same value advances as_of, so an older conflict cannot regress it.
    (STORED, revenue("$4K MRR", "2026-09-10T09:00-07:00"), "SET: revenue",
     shown("$4K MRR", "2026-09-10T09:00-07:00")),
    (STORED, revenue("$4K MRR", PAPER), "UNCHANGED: revenue", SHOWN),
    # The same instant in another offset is equal, not newer: times compare parsed, not as text.
    (STORED, revenue("$9K MRR", "2026-09-01T14:12+00:00"), REFUSED, SHOWN),
    (STORED, revenue("$1K MRR", "2026-08-01T07:00-07:00"), REFUSED, SHOWN),
    # A date-only as_of from an older record is local midnight.
    (record("2026-09-01"), revenue("$5K MRR", "2026-09-02T09:00-07:00"), "SET: revenue",
     shown("$5K MRR", "2026-09-02T09:00-07:00")),
    # A record is never replaced: a corrupt file fails by name, and a set leaves it for a human.
    ("{broken", revenue("$5K MRR", "2026-09-10T09:00-07:00"), "CORRUPT: ", "CORRUPT: "),
    ('{"facts": {"revenue": "$4K"}}', None, "CORRUPT: ", "CORRUPT: "),
])
def test_company_record(tmp_path, monkeypatch, capsys, stored, fact, printed, shown):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    if stored is not None:
        (tmp_path / "company.json").write_text(stored)
    argv = ["show"]
    if fact is not None:
        (tmp_path / "request.json").write_text(json.dumps(fact))
        argv = ["set", "--request", str(tmp_path / "request.json")]

    def run(args):
        code = company.main(args)
        out = capsys.readouterr()
        assert code == (1 if out.err else 0)
        return (out.out + out.err).strip()

    assert run(argv).startswith(printed)
    assert run(["show"]).startswith(shown)
    if printed == "CORRUPT: ":
        assert (tmp_path / "company.json").read_text() == stored


def test_concurrent_sets_all_persist(tmp_path):
    # The DM and a cron run can record facts at the same moment; neither may lose the other's.
    procs = []
    for key in company.KEYS:
        request = tmp_path / f"{key}.json"
        request.write_text(json.dumps({"key": key, "value": key, "source": "owner", "as_of": PAPER}))
        procs.append(subprocess.Popen([company.__file__, "set", "--request", str(request)],
                                      env={**os.environ, "PT_HOME": str(tmp_path)}))
    assert [p.wait() for p in procs] == [0] * len(procs)
    assert sorted(json.loads((tmp_path / "company.json").read_text())["facts"]) == sorted(company.KEYS)
