import json
import os
import subprocess

import pytest

from conftest import load_module

company = load_module("company", "pt-priority/scripts/company.py")

STORED = json.dumps({"facts": {"revenue": {"value": "$4K MRR", "source": "owner, 2026-09-01",
                                           "as_of": "2026-09-01"}}})
SHOWN = "revenue: $4K MRR (as of 2026-09-01; source: owner, 2026-09-01)"


def revenue(value, as_of):
    return {"key": "revenue", "value": value, "source": "mail sent by the owner", "as_of": as_of}


REFUSED = "REFUSED: revenue is already recorded as of 2026-09-01"


# fact None runs `show`; otherwise the fact is written to a request file and `set` reads it.
@pytest.mark.parametrize("stored, fact, printed, shown", [
    (None, None, "EMPTY", "EMPTY"),
    (STORED, revenue("$5K MRR", "2026-09-10"), "SET: revenue",
     "revenue: $5K MRR (as of 2026-09-10; source: mail sent by the owner)"),
    # Newer evidence of the same value advances as_of, so an older conflict cannot regress it.
    (STORED, revenue("$4K MRR", "2026-09-10"), "SET: revenue",
     "revenue: $4K MRR (as of 2026-09-10; source: mail sent by the owner)"),
    (STORED, revenue("$4K MRR", "2026-09-01"), "UNCHANGED: revenue", SHOWN),
    (STORED, revenue("$9K MRR", "2026-09-01"), REFUSED, SHOWN),
    (STORED, revenue("$1K MRR", "2026-08-01"), REFUSED, SHOWN),
    # A record is never replaced: a corrupt file fails by name, and a set leaves it for a human.
    ("{broken", revenue("$5K MRR", "2026-09-10"), "CORRUPT: ", "CORRUPT: "),
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
        request.write_text(json.dumps({"key": key, "value": key, "source": "owner", "as_of": "2026-09-10"}))
        procs.append(subprocess.Popen([company.__file__, "set", "--request", str(request)],
                                      env={**os.environ, "PT_HOME": str(tmp_path)}))
    assert [p.wait() for p in procs] == [0] * len(procs)
    assert sorted(json.loads((tmp_path / "company.json").read_text())["facts"]) == sorted(company.KEYS)
