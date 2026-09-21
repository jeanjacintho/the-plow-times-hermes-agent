"""owner_language.py -- the one policy for "is this owner writing Portuguese?"

This is where the tag matrix lives. Its three consumers (the chat wait lines,
the priority gap card, the unavailable-paper notice) each assert only that
they route through it, not the tag rules again.
"""
from __future__ import annotations

import pytest

from conftest import load_module

lang = load_module("owner_language", "pt-shared/scripts/owner_language.py")


@pytest.mark.parametrize("language", [
    "pt",
    "pt-BR",
    "pt-PT",          # European Portuguese -- an allow-list of two missed it
    "pt-AO",          # Angolan
    "pt_BR",          # underscore form Hermes sometimes passes through
    "pt_AO",
    "PT-br",          # case is not significant
    "Português",      # the plain-English name record_owner_language.py stores
    "portuguese",
])
def test_every_portuguese_tag_and_region(language):
    assert lang.is_portuguese(language) is True


@pytest.mark.parametrize("language", [
    "en",
    "en-GB",
    "English",
    "es-MX",          # Spanish, and notably not a pt- prefix
    "pts",            # a tag that merely starts with "pt" is not Portuguese
    "ptolemaic",
    "",
    None,
])
def test_everything_else_is_not_portuguese(language):
    assert lang.is_portuguese(language) is False
