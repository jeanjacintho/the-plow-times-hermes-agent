# Decision evals

Quality of the priority choice, not covered by unit tests. Uses a model and
is **not** part of `just test`.

```sh
uv run --no-project --python 3.13 evals/run_evals.py --model <id>
```

Needs `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY`. Target: **6/6**. If a
scenario fails, paste the failures; do not loosen `validate_priority.py`.
