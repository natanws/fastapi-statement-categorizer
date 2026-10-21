import httpx
from fastapi.testclient import TestClient

from tests.conftest import fixture_bytes


def upload(client: TestClient, name: str, account: str = "nubank", **form: str) -> httpx.Response:
    return client.post(
        "/imports",
        files={"file": (name, fixture_bytes(name))},
        data={"account": account, **form},
    )


def test_import_stores_every_row_once(client: TestClient) -> None:
    response = upload(client, "nubank.csv")

    assert response.status_code == 201
    body = response.json()
    assert (body["file_format"], body["rows_total"], body["rows_new"], body["rows_duplicate"]) == (
        "csv",
        5,
        5,
        0,
    )


def test_importing_the_same_file_twice_adds_nothing(client: TestClient) -> None:
    upload(client, "nubank.csv")

    second = upload(client, "nubank.csv").json()

    assert (second["rows_new"], second["rows_duplicate"]) == (0, 5)
    assert len(client.get("/transactions").json()) == 5


def test_imports_ofx(client: TestClient) -> None:
    body = upload(client, "sample.ofx", account="itau").json()

    assert (body["file_format"], body["rows_new"]) == ("ofx", 2)


def test_csv_layout_comes_from_the_form(client: TestClient) -> None:
    response = upload(
        client,
        "inter.csv",
        account="inter",
        date_column="Data Lançamento",
        description_column="Histórico",
        decimal_comma="true",
        delimiter=";",
    )

    assert response.status_code == 201
    amounts = {t["amount"] for t in client.get("/transactions").json()}
    assert amounts == {"-1234.56", "300.00"}


def test_malformed_file_is_rejected_and_imports_nothing(client: TestClient) -> None:
    response = client.post(
        "/imports",
        files={"file": ("bad.csv", "Data,Descrição,Valor\n01/10/2026,ok,abc\n".encode())},
        data={"account": "nubank"},
    )

    assert response.status_code == 422
    assert "line 2: invalid amount" in response.json()["detail"]
    assert client.get("/transactions").json() == []


def test_unsupported_extension_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/imports", files={"file": ("statement.pdf", b"%PDF")}, data={"account": "x"}
    )

    assert response.status_code == 422
    assert "unsupported file type" in response.json()["detail"]


def test_transactions_filter_by_month_and_account(client: TestClient) -> None:
    upload(client, "nubank.csv")
    upload(client, "sample.ofx", account="itau")

    october_itau = client.get("/transactions", params={"month": "2026-10", "account": "itau"})
    november = client.get("/transactions", params={"month": "2026-11"})

    assert {t["description"] for t in october_itau.json()} == {
        "NETFLIX.COM",
        "SALARIO ACME LTDA",
    }
    assert november.json() == []
    assert client.get("/transactions", params={"month": "2026-13"}).status_code == 422
