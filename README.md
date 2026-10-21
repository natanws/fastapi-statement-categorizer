# statement-categorizer

FastAPI service that imports bank statements (CSV and OFX), deduplicates transactions so the same
file can be imported twice safely, and categorizes them with ordered, testable rules.

## Features

**Idempotent imports.** `POST /imports` accepts CSV (configurable layout: columns, date format,
decimal comma, delimiter; Nubank's export by default) and OFX 1.x/2.x. Each transaction gets a
fingerprint from account, date, amount and normalized description, plus its occurrence number in
the file: two identical coffees on the same day are both kept, and importing the same file again
stores nothing (`rows_duplicate` tells you so). When the bank provides an id (OFX `FITID`), it
wins. A malformed file is rejected with the failing line and imports nothing.

**Ordered rules.** Rules match by `contains` or `regex` on the normalized description (case and
accents ignored), optionally by direction (debit/credit) and amount range. They run in priority
order and the first match wins. Every categorized transaction stores the `rule_id` that set it, so
a category can always be explained.

- New imports are categorized automatically.
- `POST /rules/preview` shows what a rule would match before saving it.
- `POST /categorize` applies rules to uncategorized transactions; `?overwrite=true` recomputes
  rule-based categories after editing rules.
- `PUT /transactions/{id}/category` sets a manual category, which rules never overwrite.

## Example

```bash
curl -F account=nubank -F file=@tests/fixtures/nubank.csv localhost:8000/imports
curl -X POST localhost:8000/rules -H 'Content-Type: application/json'   -d '{"name":"Rides","category":"Transport","pattern":"uber","direction":"debit"}'
curl -X POST localhost:8000/categorize
curl 'localhost:8000/transactions?month=2026-10&category=Transport'
```

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
