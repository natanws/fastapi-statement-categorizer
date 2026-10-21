from datetime import date
from decimal import Decimal

from statement_categorizer.fingerprint import fingerprints, normalize_description
from statement_categorizer.parsers import ParsedTransaction

COFFEE = ParsedTransaction(date(2026, 10, 1), "Café Central", Decimal("-8.50"))


def test_identical_rows_in_one_file_get_different_fingerprints() -> None:
    first, second = fingerprints("nubank", [COFFEE, COFFEE])

    assert first != second


def test_fingerprints_are_stable_across_imports() -> None:
    assert fingerprints("nubank", [COFFEE, COFFEE]) == fingerprints("nubank", [COFFEE, COFFEE])


def test_accent_case_and_spacing_do_not_change_the_fingerprint() -> None:
    variant = ParsedTransaction(date(2026, 10, 1), "  CAFE   central ", Decimal("-8.50"))

    assert fingerprints("nubank", [COFFEE]) == fingerprints("nubank", [variant])
    assert normalize_description("  CAFÉ   Central ") == "cafe central"


def test_account_is_part_of_the_fingerprint() -> None:
    assert fingerprints("nubank", [COFFEE]) != fingerprints("inter", [COFFEE])


def test_bank_id_wins_over_fields() -> None:
    a = ParsedTransaction(date(2026, 10, 1), "A", Decimal("1.00"), external_id="X1")
    b = ParsedTransaction(date(2026, 10, 2), "B", Decimal("2.00"), external_id="X1")

    assert fingerprints("acc", [a]) == fingerprints("acc", [b])
