import json

import pytest

from conftest import load_module

company = load_module("company", "pt-priority/scripts/company.py")

STORED = json.dumps({"facts": {"revenue": {"value": "$4K MRR", "source": "owner, 2026-09-01",
                                           "as_of": "2026-09-01"}}})
SHOWN = "revenue: $4K MRR (as of 2026-09-01; source: owner, 2026-09-01)"


def set_revenue(value, as_of):
    return ["set", "revenue", "--value", value, "--source", "mail sent by the owner", "--as-of", as_of]


@pytest.mark.parametrize("stored, argv, printed, shown", [
    (None, ["show"], "EMPTY", "EMPTY"),
    (STORED, set_revenue("$5K MRR", "2026-09-10"), "SET: revenue",
     "revenue: $5K MRR (as of 2026-09-10; source: mail sent by the owner)"),
    (STORED, set_revenue("$1K MRR", "2026-08-01"), "REFUSED: revenue is already recorded as of 2026-09-01", SHOWN),
    (STORED, set_revenue("$4K MRR", "2026-09-10"), "UNCHANGED: revenue", SHOWN),
    # A record is never replaced: a corrupt file fails by name, and a set leaves it for a human.
    ("{broken", set_revenue("$5K MRR", "2026-09-10"), "CORRUPT: ", "CORRUPT: "),
    ('{"facts": {"revenue": "$4K"}}', ["show"], "CORRUPT: ", "CORRUPT: "),
])
def test_company_record(tmp_path, monkeypatch, capsys, stored, argv, printed, shown):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    if stored is not None:
        (tmp_path / "company.json").write_text(stored)

    def run(args):
        code = company.main(args)
        out = capsys.readouterr()
        assert code == (1 if out.err else 0)
        return (out.out + out.err).strip()

    assert run(argv).startswith(printed)
    assert run(["show"]).startswith(shown)
    if printed == "CORRUPT: ":
        assert (tmp_path / "company.json").read_text() == stored
