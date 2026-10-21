from sqlalchemy import select
from sqlalchemy.orm import Session

from statement_categorizer.db import ImportBatch, Transaction
from statement_categorizer.fingerprint import fingerprints
from statement_categorizer.parsers import CsvLayout, StatementParseError, parse_csv, parse_ofx

SUPPORTED_FORMATS = ("csv", "ofx")


def detect_format(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_FORMATS:
        raise StatementParseError(
            f"unsupported file type {extension or '(none)'!r}; use CSV or OFX"
        )
    return extension


def import_statement(
    session: Session,
    *,
    account: str,
    filename: str,
    content: bytes,
    layout: CsvLayout | None = None,
) -> ImportBatch:
    """
    Parses a statement and stores only transactions not seen before.

    Parsing happens before anything is written, so a malformed file imports nothing (no half
    imports to clean up).
    """
    file_format = detect_format(filename)
    parsed = parse_ofx(content) if file_format == "ofx" else parse_csv(content, layout)
    keys = fingerprints(account, parsed)

    existing = set(
        session.scalars(select(Transaction.fingerprint).where(Transaction.fingerprint.in_(keys)))
    )
    new = [(tx, key) for tx, key in zip(parsed, keys, strict=True) if key not in existing]

    batch = ImportBatch(
        account=account,
        filename=filename,
        file_format=file_format,
        rows_total=len(parsed),
        rows_new=len(new),
        rows_duplicate=len(parsed) - len(new),
    )
    session.add(batch)
    session.flush()
    session.add_all(
        Transaction(
            account=account,
            posted_on=tx.posted_on,
            description=tx.description,
            amount=tx.amount,
            fingerprint=key,
            batch_id=batch.id,
        )
        for tx, key in new
    )
    session.commit()
    return batch
