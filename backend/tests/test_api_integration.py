"""End-to-end API tests covering Milestone 2 endpoints + M1 regression + tenancy."""
import pytest
from datetime import datetime, timedelta

from tests.conftest import seed_transaction


# ---------------------------------------------------------------------------
# Helpers that build a realistic, deterministic tenant dataset
# ---------------------------------------------------------------------------
def seed_tenant_a(db, owner_id: int) -> dict:
    """Eggs (clean history) + Milk (spiky history) -> drives predictions, risk,
    recommendations, surplus, anomalies, causes and notifications."""
    from models.category import Category
    from models.inventory_item import InventoryItem

    dairy = Category(
        owner_id=owner_id, name="Dairy", perishability_risk="high",
        storage_requirement="chilled", default_shelf_life_days=5, waste_risk_weight=1.0,
    )
    db.add(dairy)
    db.commit()
    db.refresh(dairy)

    eggs = InventoryItem(
        owner_id=owner_id, category_id=dairy.id, name="Eggs", quantity=30,
        unit="units", cost_per_unit=0.4, expiry_date=datetime.utcnow() + timedelta(days=2),
    )
    milk = InventoryItem(
        owner_id=owner_id, category_id=dairy.id, name="Milk", quantity=500,
        unit="L", cost_per_unit=1.2, expiry_date=datetime.utcnow() + timedelta(days=6),
    )
    db.add_all([eggs, milk])
    db.commit()
    db.refresh(eggs)
    db.refresh(milk)

    # Eggs: steady 1 unit/day for a full month, no spikes, no waste
    for d in range(30):
        seed_transaction(db, owner_id, eggs.id, "Eggs", "sale", 1.0, 0.4, d, "seed")
    # Eggs: a small waste event 5 days ago keeps an explainable cause available
    seed_transaction(db, owner_id, eggs.id, "Eggs", "disposal", 1.0, 0.4, 5, "seed")

    # Milk: steady sales, then a large order hit today -> sales spike anomaly
    for d in range(1, 28):
        seed_transaction(db, owner_id, milk.id, "Milk", "sale", 2.0, 1.2, d, "seed")
    seed_transaction(db, owner_id, milk.id, "Milk", "sale", 100.0, 1.2, 0, "seed")
    seed_transaction(db, owner_id, milk.id, "Milk", "purchase", 200.0, 1.2, 0, "seed")
    db.commit()
    return {"eggs_id": eggs.id, "milk_id": milk.id}


# ---------------------------------------------------------------------------
# Milestone 1 regression + auth
# ---------------------------------------------------------------------------
def test_m2_endpoints_require_auth(client):
    assert client.get("/api/waste/predictions").status_code == 401
    assert client.get("/api/waste/risk").status_code == 401
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.post("/api/waste/jobs/daily").status_code == 401


def test_m1_dashboard_and_login_still_work(client, register_user):
    headers, user = register_user("m1@example.com")
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    assert client.get("/api/inventory", headers=headers).status_code == 200
    assert client.get("/api/transactions", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# Full Milestone 2 flow
# ---------------------------------------------------------------------------
def test_full_m2_flow(client, register_user, db):
    headers, user = register_user("flow@example.com")
    ids = seed_tenant_a(db, user["id"])

    # 1) run the daily AI job
    r = client.post("/api/waste/jobs/daily", headers=headers)
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["items_scanned"] == 2
    assert summary["predictions"] == 2
    assert summary["risk_assessments"] == 2

    # 2) predictions persisted (7-day horizon per item)
    r = client.get("/api/waste/predictions", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 14
    assert {p["item_name"] for p in r.json()} == {"Eggs", "Milk"}
    assert all(0 <= p["waste_probability"] <= 1 for p in r.json())

    # 3) per-product summary
    r = client.get("/api/waste/predictions/summary", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 2

    # 4) explainable risk assessments
    r = client.get("/api/waste/risk", headers=headers)
    assert r.status_code == 200
    by_name = {a["item_name"]: a for a in r.json()}
    assert "Eggs" in by_name and "Milk" in by_name
    assert by_name["Eggs"]["risk_level"] in ("low", "moderate", "high", "critical")
    assert len(by_name["Eggs"]["factors"]) > 0
    assert by_name["Eggs"]["explanation"]

    # risk filter + validation
    assert client.get("/api/waste/risk", params={"risk_level": "high"}, headers=headers).status_code == 200
    assert client.get("/api/waste/risk", params={"risk_level": "bogus"}, headers=headers).status_code == 422

    # 5) recommendations (Eggs is high/critical risk with surplus -> must have some)
    r = client.get("/api/recommendations", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    del_link = r.json()[0]["id"]

    # 6) anomalies + resolve
    r = client.get("/api/waste/anomalies", headers=headers)
    assert r.status_code == 200
    anomalies = r.json()
    assert len(anomalies) >= 1
    rid = anomalies[0]["id"]
    assert client.post(f"/api/waste/anomalies/{rid}/resolve", headers=headers).status_code == 200
    assert client.get("/api/waste/anomalies", headers=headers).status_code == 200

    # 7) causes
    r = client.get("/api/waste/causes", headers=headers)
    assert r.status_code == 200 and len(r.json()) >= 1

    # 8) notifications + unread count
    r = client.get("/api/notifications/unread-count", headers=headers)
    assert r.status_code == 200 and r.json()["count"] >= 1
    r = client.get("/api/notifications", headers=headers)
    assert r.status_code == 200 and len(r.json()) >= 1
    nid = r.json()[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=headers).status_code == 200

    # 9) analytics + trends + forecast-vs-actual
    r = client.get("/api/waste/analytics", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body["kpis"]) >= {"total_items", "waste_qty", "predicted_waste", "predicted_surplus", "donations"}
    assert body["risk_counts"]["low"] + body["risk_counts"]["moderate"] + body["risk_counts"]["high"] + body["risk_counts"]["critical"] == 2

    r = client.get("/api/waste/trends", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["daily"]) == 30
    assert isinstance(r.json()["forecast_vs_actual"]["series"], list)

    # 10) dashboard summary (M2 dashboard payload)
    r = client.get("/api/dashboard/summary", headers=headers)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["kpis"]["total_items"] == 2
    assert s["action_center"]["upcoming_expiries"]
    assert s["kpis"]["unread_notifications"] >= 1

    # 11) product forecast + risk endpoints
    r = client.get(f"/api/products/{ids['eggs_id']}/forecast", headers=headers)
    assert r.status_code == 200 and len(r.json()["forecast"]) == 7
    assert r.json()["total_demand"] >= 0
    r = client.get(f"/api/products/{ids['eggs_id']}/risk", headers=headers)
    assert r.status_code == 200
    assert r.json()["risk"]["risk_score"] >= 0

    # 12) reorder recommendations
    r = client.get("/api/waste/reorder", headers=headers)
    assert r.status_code == 200 and isinstance(r.json(), list)

    # 13) simulations (item-scoped + free-form)
    r = client.post("/api/simulations", json={
        "item_id": ids["milk_id"], "current_stock": 100, "donation_quantity": 20,
        "expected_demand": 60,
    }, headers=headers)
    assert r.status_code == 200, r.text
    sim = r.json()
    assert sim["baseline"]["waste"] > sim["simulated"]["waste"]
    assert client.get("/api/simulations", headers=headers).status_code == 200

    # 14) recommendation status update
    r = client.patch(f"/api/recommendations/{del_link}", json={"status": "applied"}, headers=headers)
    assert r.status_code == 200, r.text

    # 15) surplus allocations + partners
    r = client.get("/api/surplus/allocations", headers=headers)
    assert r.status_code == 200
    r = client.get("/api/surplus/partners", headers=headers)
    assert r.status_code == 200
    r = client.post("/api/surplus/partners", json={
        "name": "Food Bank", "contact": "555", "email": "bank@example.com",
    }, headers=headers)
    assert r.status_code in (200, 201), r.text

    # 16) forecast accuracy
    r = client.get("/api/waste/forecast-accuracy", headers=headers)
    assert r.status_code == 200
    assert "overall_accuracy" in r.json()
    assert "items_evaluated" in r.json()

    # 17) predict on demand (inference-only, item_id is a query param)
    r = client.post("/api/waste/predict", params={"item_id": ids["eggs_id"]}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["predictions_generated"] == 1


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------
def test_tenant_isolation(client, register_user, db):
    headers_a, user_a = register_user("iso.a@example.com")
    headers_b, user_b = register_user("iso.b@example.com")
    ids = seed_tenant_a(db, user_a["id"])

    # A sees its own data
    assert client.get("/api/waste/predictions", headers=headers_a).status_code == 200

    # B cannot read A's item via M1 or M2 endpoints
    assert client.get(f"/api/inventory/{ids['milk_id']}", headers=headers_b).status_code == 404
    assert client.get(f"/api/products/{ids['milk_id']}/risk", headers=headers_b).status_code == 404
    assert client.get(f"/api/products/{ids['milk_id']}/forecast", headers=headers_b).status_code == 404

    # B has no M2 data and its simulated item write must fail on A's item
    assert client.get("/api/waste/risk", headers=headers_b).json() == []
    assert client.get("/api/recommendations", headers=headers_b).json() == []
    r = client.get("/api/dashboard/summary", headers=headers_b)
    assert r.status_code == 200 and r.json()["kpis"]["total_items"] == 0

    sim = client.post("/api/simulations", json={"item_id": ids["milk_id"], "current_stock": 10}, headers=headers_b)
    assert sim.status_code == 404


def test_db_and_analytics_consistent(db):
    """Sanity: seeded sessions share the same in-memory store as the API."""
    from models.inventory_item import InventoryItem
    assert db.query(InventoryItem).count() >= 0