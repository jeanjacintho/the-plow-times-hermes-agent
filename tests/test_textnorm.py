from conftest import load_module

tn = load_module("textnorm", "pt-shared/scripts/textnorm.py")


def test_normalize():
    assert tn.normalize("  “Raise”  $1.5M — by Sép 30! ") == "raise 1 5m by sep 30"


def test_similar():
    assert tn.similar("Close the seed extension with Fund X", "close seed extension - Fund X")
    assert not tn.similar("Close the seed extension", "Hire a designer")
    assert not tn.similar("", "")
