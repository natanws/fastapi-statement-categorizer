# statement-categorizer

FastAPI service that imports bank statements (CSV and OFX), deduplicates transactions so the same
file can be imported twice safely, and categorizes them with ordered, testable rules.

> Status: work in progress. This README tracks what is already implemented.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install --hook-type pre-commit --hook-type commit-msg
uvicorn statement_categorizer.main:app --reload   # http://localhost:8000/docs
pytest
```

## Development workflow

- `main` is protected: changes land through pull requests.
- CI runs on every PR: Ruff (lint + format), mypy in strict mode, pytest with coverage,
  [Conventional Commits](https://www.conventionalcommits.org/) on every commit and on the PR title.
- pre-commit runs Ruff and checks the commit message locally.

## License

MIT
