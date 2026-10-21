from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from statement_categorizer.db import Database, Transaction
from statement_categorizer.importer import import_statement
from statement_categorizer.parsers import CsvLayout, StatementParseError
from statement_categorizer.schemas import ImportResult, TransactionOut

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def get_session(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.database
    yield from database.session()


SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter()


@router.post("/imports", response_model=ImportResult, status_code=201, tags=["imports"])
async def create_import(
    session: SessionDep,
    file: Annotated[UploadFile, File(description="CSV or OFX statement")],
    account: Annotated[str, Form(min_length=1, max_length=64)],
    date_column: Annotated[str, Form()] = "Data",
    description_column: Annotated[str, Form()] = "Descrição",
    amount_column: Annotated[str, Form()] = "Valor",
    date_format: Annotated[str, Form()] = "%d/%m/%Y",
    decimal_comma: Annotated[bool, Form()] = False,
    delimiter: Annotated[str, Form(min_length=1, max_length=1)] = ",",
) -> ImportResult:
    """Imports a statement. Importing the same file again stores nothing new (see rows_duplicate).

    The column fields only apply to CSV files and describe the bank's export layout.
    """
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file larger than 5 MB")

    layout = CsvLayout(
        date_column=date_column,
        description_column=description_column,
        amount_column=amount_column,
        date_format=date_format,
        decimal_comma=decimal_comma,
        delimiter=delimiter,
    )
    try:
        batch = import_statement(
            session,
            account=account,
            filename=file.filename or "",
            content=content,
            layout=layout,
        )
    except StatementParseError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ImportResult.model_validate(batch)


def _month_range(month: str) -> tuple[date, date]:
    try:
        year, number = (int(part) for part in month.split("-"))
        start = date(year, number, 1)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM") from error
    end = date(year + (number == 12), number % 12 + 1, 1)
    return start, end


@router.get("/transactions", response_model=list[TransactionOut], tags=["transactions"])
def list_transactions(
    session: SessionDep,
    account: str | None = None,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", examples=["2026-10"])] = None,
    category: str | None = None,
    uncategorized: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Transaction]:
    query = select(Transaction).order_by(Transaction.posted_on.desc(), Transaction.id.desc())
    if account:
        query = query.where(Transaction.account == account)
    if month:
        start, end = _month_range(month)
        query = query.where(Transaction.posted_on >= start, Transaction.posted_on < end)
    if category:
        query = query.where(Transaction.category == category)
    if uncategorized:
        query = query.where(Transaction.category.is_(None))
    return list(session.scalars(query.limit(limit).offset(offset)))
