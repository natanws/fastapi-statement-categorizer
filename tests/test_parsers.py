from datetime import date
from decimal import Decimal

import pytest

from statement_categorizer.parsers import CsvLayout, StatementParseError, parse_csv, parse_ofx
from tests.conftest import fixture_bytes


def test_parses_nubank_csv_with_default_layout() -> None:
    rows = parse_csv(fixture_bytes("nubank.csv"))

    assert len(rows) == 5
    assert rows[0].posted_on == date(2026, 10, 1)
    assert rows[0].description == "Padaria Pão Quente"
    assert rows[0].amount == Decimal("-32.90")


def test_parses_semicolon_csv_with_decimal_comma() -> None:
    layout = CsvLayout(
        date_column="Data Lançamento",
        description_column="Histórico",
        amount_column="Valor",
        decimal_comma=True,
        delimiter=";",
    )

    rows = parse_csv(fixture_bytes("inter.csv"), layout)

    assert [r.amount for r in rows] == [Decimal("-1234.56"), Decimal("300.00")]


def test_reports_missing_columns() -> None:
    with pytest.raises(StatementParseError, match="missing column"):
        parse_csv(b"Date,Amount\n2026-10-01,10\n")


def test_reports_the_line_with_a_bad_value() -> None:
    content = "Data,Descrição,Valor\n01/10/2026,ok,1.00\n31/02/2026,bad,2.00\n".encode()

    with pytest.raises(StatementParseError, match="line 3: invalid date"):
        parse_csv(content)


def test_skips_blank_lines_and_strips_bom() -> None:
    content = "﻿Data,Descrição,Valor\n01/10/2026,ok,1.00\n,,\n".encode()

    assert len(parse_csv(content)) == 1


def test_parses_ofx_sgml_with_fitid() -> None:
    rows = parse_ofx(fixture_bytes("sample.ofx"))

    assert [(r.posted_on, r.description, r.amount, r.external_id) for r in rows] == [
        (date(2026, 10, 3), "NETFLIX.COM", Decimal("-59.90"), "202610030001"),
        (date(2026, 10, 5), "SALARIO ACME LTDA", Decimal("5200.00"), "202610050001"),
    ]


def test_rejects_files_that_are_not_ofx() -> None:
    with pytest.raises(StatementParseError, match="not an OFX file"):
        parse_ofx(b"hello")
