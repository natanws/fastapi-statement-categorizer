from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from statement_categorizer.api import SessionDep
from statement_categorizer.db import Rule, Transaction
from statement_categorizer.rules import InvalidRuleError, categorize, compile_rule

router = APIRouter(tags=["rules"])


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=100, ge=0, le=10_000)
    match_type: Literal["contains", "regex"] = "contains"
    pattern: str = Field(min_length=1, max_length=200)
    direction: Literal["debit", "credit", "any"] = "any"
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    enabled: bool = True


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PreviewOut(BaseModel):
    matches: int
    sample: list[str]


class CategorizeOut(BaseModel):
    evaluated: int
    categorized: int
    unmatched: int


class ManualCategoryIn(BaseModel):
    category: str | None = Field(default=None, max_length=64)


def _validate(rule: RuleIn) -> None:
    try:
        compile_rule(rule_id=None, **rule.model_dump(exclude={"name", "priority", "enabled"}))
    except InvalidRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/rules", response_model=list[RuleOut])
def list_rules(session: SessionDep) -> list[Rule]:
    return list(session.scalars(select(Rule).order_by(Rule.priority, Rule.id)))


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(session: SessionDep, body: RuleIn) -> Rule:
    _validate(body)
    rule = Rule(**body.model_dump())
    session.add(rule)
    session.commit()
    return rule


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(session: SessionDep, rule_id: int, body: RuleIn) -> Rule:
    rule = session.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    _validate(body)
    for field, value in body.model_dump().items():
        setattr(rule, field, value)
    session.commit()
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(session: SessionDep, rule_id: int) -> None:
    rule = session.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    session.delete(rule)
    session.commit()


@router.post("/rules/preview", response_model=PreviewOut)
def preview_rule(session: SessionDep, body: RuleIn) -> PreviewOut:
    """Dry run: which transactions would this rule match? Nothing is saved."""
    _validate(body)
    compiled = compile_rule(
        rule_id=None, **body.model_dump(exclude={"name", "priority", "enabled"})
    )
    matched = [
        tx.description
        for tx in session.scalars(select(Transaction))
        if compiled.matches(tx.description, tx.amount)
    ]
    return PreviewOut(matches=len(matched), sample=matched[:10])


@router.post("/categorize", response_model=CategorizeOut)
def run_categorize(
    session: SessionDep,
    overwrite: Annotated[
        bool, Query(description="Recompute rule-based categories too (manual ones are kept).")
    ] = False,
) -> CategorizeOut:
    result = categorize(session, session.scalars(select(Transaction)).all(), overwrite=overwrite)
    return CategorizeOut(**result.__dict__)


@router.put("/transactions/{transaction_id}/category", tags=["transactions"])
def set_category(
    session: SessionDep, transaction_id: int, body: ManualCategoryIn
) -> dict[str, str | int | None]:
    """Manual override. Setting null hands the transaction back to the rules."""
    tx = session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    tx.category = body.category
    tx.category_source = "manual" if body.category else None
    tx.rule_id = None
    session.commit()
    return {"id": tx.id, "category": tx.category, "category_source": tx.category_source}
