from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import fixture_bytes


def import_nubank(client: TestClient) -> None:
    response = client.post(
        "/imports",
        files={"file": ("nubank.csv", fixture_bytes("nubank.csv"))},
        data={"account": "nubank"},
    )
    assert response.status_code == 201


def create_rule(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/rules", json={"name": body.get("category", "rule"), **body})
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def categories(client: TestClient) -> dict[str, str | None]:
    return {t["description"]: t["category"] for t in client.get("/transactions").json()}


def test_rules_categorize_new_imports_automatically(client: TestClient) -> None:
    create_rule(client, category="Food", pattern="café")
    create_rule(client, category="Transport", pattern="uber")

    import_nubank(client)

    assert categories(client) == {
        "Padaria Pão Quente": None,
        "Café Central": "Food",
        "Transferência recebida - Salário": None,
        "Uber *Trip": "Transport",
    }


def test_rule_id_explains_the_category(client: TestClient) -> None:
    food = create_rule(client, category="Food", pattern="padaria")
    import_nubank(client)

    bakery = next(t for t in client.get("/transactions").json() if t["category"] == "Food")

    assert (bakery["rule_id"], bakery["category_source"]) == (food["id"], "rule")


def test_categorize_endpoint_applies_rules_created_after_the_import(client: TestClient) -> None:
    import_nubank(client)
    create_rule(client, category="Income", pattern="salario", direction="credit")

    result = client.post("/categorize").json()

    assert result == {"evaluated": 5, "categorized": 1, "unmatched": 4}
    assert categories(client)["Transferência recebida - Salário"] == "Income"


def test_priority_decides_between_overlapping_rules(client: TestClient) -> None:
    create_rule(client, category="Generic", pattern="caf", priority=200)
    create_rule(client, category="Coffee", pattern="cafe central", priority=10)

    import_nubank(client)

    assert categories(client)["Café Central"] == "Coffee"


def test_manual_category_survives_recategorization(client: TestClient) -> None:
    create_rule(client, category="Transport", pattern="uber")
    import_nubank(client)
    uber = next(t for t in client.get("/transactions").json() if t["category"] == "Transport")

    client.put(f"/transactions/{uber['id']}/category", json={"category": "Work travel"})
    client.post("/categorize", params={"overwrite": True})

    assert categories(client)["Uber *Trip"] == "Work travel"


def test_overwrite_recomputes_rule_categories_after_editing_a_rule(client: TestClient) -> None:
    rule = create_rule(client, category="Food", pattern="padaria")
    import_nubank(client)

    client.put(f"/rules/{rule['id']}", json={**rule, "category": "Bakery"})
    client.post("/categorize", params={"overwrite": True})

    assert categories(client)["Padaria Pão Quente"] == "Bakery"


def test_preview_does_not_save_anything(client: TestClient) -> None:
    import_nubank(client)

    preview = client.post(
        "/rules/preview", json={"name": "p", "category": "Food", "pattern": "café"}
    ).json()

    assert preview == {"matches": 2, "sample": ["Café Central", "Café Central"]}
    assert client.get("/rules").json() == []
    assert set(categories(client).values()) == {None}


def test_invalid_regex_is_a_validation_error(client: TestClient) -> None:
    response = client.post(
        "/rules", json={"name": "bad", "category": "x", "match_type": "regex", "pattern": "("}
    )

    assert response.status_code == 422
    assert "invalid regex" in response.json()["detail"]


def test_deleting_a_rule_keeps_existing_categories(client: TestClient) -> None:
    rule = create_rule(client, category="Food", pattern="padaria")
    import_nubank(client)

    assert client.delete(f"/rules/{rule['id']}").status_code == 204
    assert categories(client)["Padaria Pão Quente"] == "Food"
    assert client.delete(f"/rules/{rule['id']}").status_code == 404
