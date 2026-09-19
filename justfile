# Run the whole suite: this agent's contracts and the pt- skill scripts.
#
# Same runner the sibling agents use -- uv, no project, pinned pytest -- so a
# checkout needs nothing installed beyond uv itself.
# plow-wiki is the wiki the Mac runs: the tests validate every page against it.
test:
    uv run --no-project --python 3.13 --with pytest==8.4.2 --with "plow-wiki @ git+https://github.com/plow-pbc/plow-wiki@v0.2.0" pytest -q tests/