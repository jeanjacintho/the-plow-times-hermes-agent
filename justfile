# Run the whole suite: this agent's contracts and the pt- skill scripts.
#
# Same runner the sibling agents use -- uv, no project, pinned pytest -- so a
# checkout needs nothing installed beyond uv itself.
# plow-wiki is the wiki the Mac runs: the tests validate every page against it,
# pinned to v0.2.0 by commit (a tag can move; a commit can't).
test:
    uv run --no-project --python 3.13 --with pytest==8.4.2 --with "plow-wiki @ git+https://github.com/plow-pbc/plow-wiki@4faad4d9c9b15e3fb1ea6919e7334a814270e02e" pytest -q tests/