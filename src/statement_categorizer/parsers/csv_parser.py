import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from statement_categorizer.parsers.base import ParsedTransaction, StatementParseError


@dataclass(frozen=True)
class CsvLayout:
    """Where each field lives in a bank's CSV export. Defaults match Nubank's account export."""

    date_column: str = "Data"
    description_column: str = "Descrição"
    amount_column: str = "Valor"
    date_format: str = "%d/%m/%Y"
    # Brazilian exports often write 1.234,56; set to True to read that format.
    decimal_comma: bool = False
    delimiter: str = ","


def _parse_amount(raw: str, decimal_comma: bool) -> Decimal:
    text = raw.strip().replace("R$", "").replace(" ", "")
    if decimal_comma:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation as error:
        raise ValueError(f"invalid amount {raw!r}") from error


def _parse_date(raw: str, date_format: str) -> date:
    try:
        return datetime.strptime(raw.strip(), date_format).date()
    except ValueError as error:
        raise ValueError(f"invalid date {raw!r} (expected {date_format})") from error


def parse_csv(content: bytes, layout: CsvLayout | None = None) -> list[ParsedTransaction]:
    layout = layout or CsvLayout()
    # utf-8-sig drops the BOM that Excel-exported files often start with.
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=layout.delimiter)

    required = {layout.date_column, layout.description_column, layout.amount_column}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise StatementParseError(f"missing column(s): {', '.join(sorted(missing))}")

    transactions: list[ParsedTransaction] = []
    for line, row in enumerate(reader, start=2):  # line 1 is the header
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            transactions.append(
                ParsedTransaction(
                    posted_on=_parse_date(row[layout.date_column], layout.date_format),
                    description=row[layout.description_column].strip(),
                    amount=_parse_amount(row[layout.amount_column], layout.decimal_comma),
                )
            )
        except ValueError as error:
            raise StatementParseError(f"line {line}: {error}") from error
    return transactions
