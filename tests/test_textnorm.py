from conftest import load_module

tn = load_module("textnorm", "pt-shared/scripts/textnorm.py")


def test_normalize():
    assert tn.normalize("  “Raise”  $1.5M — by Sép 30! ") == "raise 1 5m by sep 30"


def test_similar():
    assert tn.similar("Close the seed extension with Fund X", "close seed extension - Fund X")
    assert not tn.similar("Close the seed extension", "Hire a designer")
    assert not tn.similar("", "")


def test_stems_gerund_and_plural():
    assert tn._stem("leading") == "lead"
    assert tn._stem("reps") == "rep"


def test_similar_hire_rep_matches_adding_reps():
    assert tn._tokens("hire another rep") & tn._tokens("adding reps") == {"rep"}
    assert tn.similar(
        "Hire another rep before the ramp model works",
        "Adding reps before the ramp model works",
        tn.AVOID_THRESHOLD,
    )
