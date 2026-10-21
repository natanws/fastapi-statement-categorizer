import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from statement_categorizer.db import Rule, Transaction
from statement_categorizer.fingerprint import normalize_description

MatchType = Literal["contains", "regex"]
Direction = Literal["debit", "credit", "any"]


class InvalidRuleError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledRule:
    """A rule ready to evaluate: the pattern is validated and compiled once, not per transaction."""

    id: int | None
    category: str
    regex: re.Pattern[str]
    direction: Direction
    min_amount: Decimal | None
    max_amount: Decimal | None

    def matches(self, description: str, amount: Decimal) -> bool:
        if self.direction == "debit" and amount >= 0:
            return False
        if self.direction == "credit" and amount <= 0:
            return False
        # Limits compare absolute values: "between 10 and 50" reads naturally for expenses too.
        magnitude = abs(amount)
        if self.min_amount is not None and magnitude < self.min_amount:
            return False
        if self.max_amount is not None and magnitude > self.max_amount:
            return False
        return self.regex.search(normalize_description(description)) is not None


def compile_rule(
    *,
    rule_id: int | None,
    category: str,
    match_type: str,
    pattern: str,
    direction: str = "any",
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> CompiledRule:
    if direction not in ("debit", "credit", "any"):
        raise InvalidRuleError("direction must be debit, credit or any")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise InvalidRuleError("min_amount cannot be greater than max_amount")
    # Descriptions are normalized (lowercase, no accents) before matching; the pattern too, so
    # "Café" in a rule matches "CAFE" in a statement.
    normalized = normalize_description(pattern)
    if match_type == "contains":
        regex = re.compile(re.escape(normalized))
    elif match_type == "regex":
        try:
            regex = re.compile(normalized)
        except re.error as error:
            raise InvalidRuleError(f"invalid regex: {error}") from error
    else:
        raise InvalidRuleError("match_type must be contains or regex")
    return CompiledRule(
        rule_id, category, regex, cast(Direction, direction), min_amount, max_amount
    )


def compile_stored(rule: Rule) -> CompiledRule:
    return compile_rule(
        rule_id=rule.id,
        category=rule.category,
        match_type=rule.match_type,
        pattern=rule.pattern,
        direction=rule.direction,
        min_amount=rule.min_amount,
        max_amount=rule.max_amount,
    )


def load_rules(session: Session) -> list[CompiledRule]:
    rules = session.scalars(
        select(Rule).where(Rule.enabled.is_(True)).order_by(Rule.priority, Rule.id)
    )
    return [compile_stored(rule) for rule in rules]


def first_match(
    rules: Sequence[CompiledRule], description: str, amount: Decimal
) -> CompiledRule | None:
    return next((rule for rule in rules if rule.matches(description, amount)), None)


@dataclass(frozen=True)
class CategorizeResult:
    evaluated: int
    categorized: int
    unmatched: int


def categorize(
    session: Session, transactions: Iterable[Transaction], *, overwrite: bool = False
) -> CategorizeResult:
    """
    Applies the enabled rules. Manual categories are always kept; rule-based ones are only
    recomputed when overwrite=True (e.g. after editing rules).
    """
    rules = load_rules(session)
    evaluated = categorized = 0
    for tx in transactions:
        if tx.category_source == "manual" or (tx.category is not None and not overwrite):
            continue
        evaluated += 1
        rule = first_match(rules, tx.description, tx.amount)
        tx.category = rule.category if rule else None
        tx.category_source = "rule" if rule else None
        tx.rule_id = rule.id if rule else None
        categorized += rule is not None
    session.commit()
    return CategorizeResult(evaluated, categorized, evaluated - categorized)
