from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from statement_categorizer.db import Database
from statement_categorizer.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def database() -> Database:
    return Database("sqlite://")


@pytest.fixture
def client(database: Database) -> Iterator[TestClient]:
    with TestClient(create_app(database)) as test_client:
        yield test_client


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
