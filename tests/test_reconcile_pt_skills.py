"""reconcile_pt_skills.py — agent-mgr re-seed of unedited pt-* skills."""
from __future__ import annotations

from conftest import load_module

rec = load_module("reconcile_pt_skills", "pt-shared/scripts/reconcile_pt_skills.py")


def write_skill(path, name, body="hello"):
    d = path / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n{body}\n", encoding="utf-8")
    return d


def test_seeds_when_absent(tmp_path):
    checkout = tmp_path / "repo"
    write_skill(checkout, "pt-demo", "v1")
    home = tmp_path / "home"
    out = rec.reconcile(checkout, home)
    assert (home / "skills" / "pt-demo" / "SKILL.md").read_text().endswith("v1\n")
    assert "seeded pt-demo" in out
    stamp = (home / "skills" / "pt-demo" / rec.STAMP).read_text().strip()
    assert len(stamp) == 32


def test_updates_unstamped_legacy_copy(tmp_path):
    checkout = tmp_path / "repo"
    write_skill(checkout, "pt-demo", "v2")
    dest = tmp_path / "home" / "skills" / "pt-demo"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("---\nname: pt-demo\n---\nold\n", encoding="utf-8")
    rec.reconcile(checkout, tmp_path / "home")
    assert (dest / "SKILL.md").read_text().endswith("v2\n")


def test_updates_pristine_stamped_copy(tmp_path):
    checkout = tmp_path / "repo"
    src = write_skill(checkout, "pt-demo", "v1")
    home = tmp_path / "home"
    rec.reconcile(checkout, home)
    (src / "SKILL.md").write_text("---\nname: pt-demo\n---\nv2\n", encoding="utf-8")
    rec.reconcile(checkout, home)
    assert (home / "skills" / "pt-demo" / "SKILL.md").read_text().endswith("v2\n")


def test_keeps_user_modified_copy(tmp_path):
    checkout = tmp_path / "repo"
    src = write_skill(checkout, "pt-demo", "v1")
    home = tmp_path / "home"
    rec.reconcile(checkout, home)
    dest = home / "skills" / "pt-demo"
    (dest / "SKILL.md").write_text("---\nname: pt-demo\n---\nagent edit\n", encoding="utf-8")
    (src / "SKILL.md").write_text("---\nname: pt-demo\n---\nv2\n", encoding="utf-8")
    out = rec.reconcile(checkout, home)
    assert "keeping user-modified pt-demo" in out
    assert (dest / "SKILL.md").read_text().endswith("agent edit\n")


def test_skips_when_already_current(tmp_path):
    checkout = tmp_path / "repo"
    write_skill(checkout, "pt-demo", "v1")
    home = tmp_path / "home"
    rec.reconcile(checkout, home)
    out = rec.reconcile(checkout, home)
    assert "already current pt-demo" in out
