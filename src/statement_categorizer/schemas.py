from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ImportResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account: str
    filename: str
    file_format: str
    rows_total: int
    rows_new: int
    rows_duplicate: int
    imported_at: datetime


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account: str
    posted_on: date
    description: str
    amount: Decimal
    category: str | None
