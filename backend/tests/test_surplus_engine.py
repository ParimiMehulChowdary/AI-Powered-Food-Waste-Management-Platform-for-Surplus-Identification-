from services.surplus_engine import allocate_for_item, urgency_sort_key


def test_no_surplus_returns_none(db):
    from models.inventory_item import InventoryItem
    item = InventoryItem(owner_id=1, name="Apple", quantity=5, unit="kg")
    db.add(item)
    db.commit()
    assert allocate_for_item(db, item, {"total_demand": 8, "total_surplus": 0}, {}) is None


def test_surplus_creates_allocation(db):
    from models.inventory_item import InventoryItem
    item = InventoryItem(owner_id=1, name="Tomato", quantity=50, unit="kg")
    db.add(item)
    db.commit()
    result = allocate_for_item(
        db, item,
        {"total_demand": 20, "total_surplus": 30, "days_to_expiry": 5},
        {"risk_level": "high"},
    )
    assert result is not None
    assert result["surplus_quantity"] == 30
    assert result["allocation_type"] in ("donation", "promotion")
    assert result["urgency"] in ("low", "medium", "high", "critical") or 1 <= result["urgency"] <= 4
    assert "suggested_partner" in result


def test_expired_surplus_rejected(db):
    from models.inventory_item import InventoryItem
    item = InventoryItem(owner_id=1, name="Yogurt", quantity=50, unit="kg")
    db.add(item)
    db.commit()
    result = allocate_for_item(
        db, item,
        {"total_demand": 20, "total_surplus": 30, "days_to_expiry": -2},
        {"risk_level": "critical"},
    )
    assert result is None  # no safe period, no allocation


def test_urgency_sort_key_orders_high_first():
    items = [
        {"urgency": 4, "surplus_quantity": 1},
        {"urgency": 1, "surplus_quantity": 5},
        {"urgency": 2, "surplus_quantity": 3},
    ]
    assert sorted(items, key=urgency_sort_key)[0]["urgency"] == 1