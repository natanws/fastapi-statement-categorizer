from decimal import Decimal

import pytest

from statement_categorizer.rules import InvalidRuleError, compile_rule, first_match


def test_contains_ignores_case_and_accents() -> None:
    cafe = compile_rule(rule_id=1, category="Food", match_type="contains", pattern="Café")

    assert cafe.matches("CAFE CENTRAL", Decimal("-8.50"))
    assert not cafe.matches("Padaria", Decimal("-8.50"))


def test_contains_treats_regex_characters_literally() -> None:
    uber = compile_rule(rule_id=1, category="Transport", match_type="contains", pattern="uber *")

    assert uber.matches("Uber *Trip", Decimal("-20"))
    assert not uber.matches("Uber Eats", Decimal("-20"))


def test_regex_rules() -> None:
    streaming = compile_rule(
        rule_id=1, category="Subscriptions", match_type="regex", pattern=r"netflix|spotify"
    )

    assert streaming.matches("NETFLIX.COM", Decimal("-59.90"))
    assert streaming.matches("Spotify P1", Decimal("-21.90"))


def test_direction_and_amount_limits() -> None:
    salary = compile_rule(
        rule_id=1,
        category="Income",
        match_type="contains",
        pattern="salario",
        direction="credit",
        min_amount=Decimal("1000"),
    )

    assert salary.matches("SALARIO ACME", Decimal("5200"))
    assert not salary.matches("SALARIO ACME", Decimal("-5200"))  # wrong direction
    assert not salary.matches("SALARIO ACME", Decimal("500"))  # below the minimum


def test_first_matching_rule_wins() -> None:
    specific = compile_rule(rule_id=1, category="Ride", match_type="contains", pattern="uber trip")
    generic = compile_rule(rule_id=2, category="Uber", match_type="contains", pattern="uber")

    assert first_match([specific, generic], "Uber Trip", Decimal("-10")) is specific
    assert first_match([specific, generic], "Uber Eats", Decimal("-10")) is generic
    assert first_match([specific, generic], "Padaria", Decimal("-10")) is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"match_type": "regex", "pattern": "("}, "invalid regex"),
        ({"match_type": "glob", "pattern": "x"}, "match_type"),
        ({"match_type": "contains", "pattern": "x", "direction": "up"}, "direction"),
        (
            {
                "match_type": "contains",
                "pattern": "x",
                "min_amount": Decimal("10"),
                "max_amount": Decimal("1"),
            },
            "min_amount",
        ),
    ],
)
def test_invalid_rules_are_rejected(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidRuleError, match=message):
        compile_rule(rule_id=None, category="x", **kwargs)  # type: ignore[arg-type]
