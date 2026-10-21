import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from statement_categorizer.parsers.base import ParsedTransaction, StatementParseError

_TRANSACTION = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.S)


def _field(block: str, tag: str) -> str | None:
    """Reads <TAG>value from OFX 1.x (SGML, closing tags optional) and OFX 2.x (XML)."""
    match = re.search(rf"<{tag}>([^<\r\n]*)", block)
    return match.group(1).strip() if match else None


def _parse_date(raw: str) -> date:
    # OFX dates are YYYYMMDD optionally followed by time and timezone: 20261003120000[-3:BRT]
    return datetime.strptime(raw[:8], "%Y%m%d").date()


def parse_ofx(content: bytes) -> list[ParsedTransaction]:
    # Brazilian banks still export OFX 1.x in latin-1; try UTF-8 first.
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    if "<OFX>" not in text.upper():
        raise StatementParseError("not an OFX file (missing <OFX> element)")

    transactions: list[ParsedTransaction] = []
    for index, match in enumerate(_TRANSACTION.finditer(text), start=1):
        block = match.group(1)
        posted = _field(block, "DTPOSTED")
        amount = _field(block, "TRNAMT")
        description = _field(block, "MEMO") or _field(block, "NAME")
        if not posted or not amount or not description:
            raise StatementParseError(
                f"transaction {index}: DTPOSTED, TRNAMT and MEMO/NAME are required"
            )
        try:
            transactions.append(
                ParsedTransaction(
                    posted_on=_parse_date(posted),
                    description=description,
                    amount=Decimal(amount.replace(",", ".")).quantize(Decimal("0.01")),
                    external_id=_field(block, "FITID"),
                )
            )
        except (ValueError, InvalidOperation) as error:
            raise StatementParseError(f"transaction {index}: {error}") from error
    return transactions
