from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class StatementParseError(ValueError):
    """The file is not in the expected format. The message says which line failed and why."""


@dataclass(frozen=True)
class ParsedTransaction:
    posted_on: date
    description: str
    amount: Decimal
    # Bank-provided id (OFX FITID) when available; it identifies the transaction better than
    # anything derived from its fields.
    external_id: str | None = None
