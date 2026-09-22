from services.cause_classifier import classify_item


def _mk_item(db, owner_id, name, **kw):
    from models.inventory_item import InventoryItem
    item = InventoryItem(owner_id=owner_id, name=name, quantity=1, unit="units", **kw)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_no_waste_means_no_cause(db):
    item = _mk_item(db, 1, "Rice")
    for d in range(10):
        from tests.conftest import seed_transaction
        seed_transaction(db, 1, item.id, "Rice", "sale", 1.0, 1.0, d)
    db.commit()
    assert classify_item(db, item, None) is None


def test_overstocking_cause_from_purchase_ratio(db):
    item = _mk_item(db, 2, "Bread")
    from tests.conftest import seed_transaction
    # heavy purchasing vs low sales -> overstocking
    for d in range(1, 6):
        seed_transaction(db, 2, item.id, "Bread", "purchase", 10.0, 1.0, d)
        seed_transaction(db, 2, item.id, "Bread", "sale", 1.0, 1.0, d)
        seed_transaction(db, 2, item.id, "Bread", "disposal", 3.0, 1.0, d)
    db.commit()
    result = classify_item(db, item, None)
    assert result["cause"] == "overstocking"
    assert result["confidence"] > 0.5


def test_expiry_cause_from_recent_purchases(db):
    from datetime import datetime, timedelta
    item = _mk_item(db, 3, "Yogurt", expiry_date=datetime.utcnow() + timedelta(days=1))
    from tests.conftest import seed_transaction
    # purchase 2 days before the waste peak, on a perishable item
    seed_transaction(db, 3, item.id, "Yogurt", "purchase", 20.0, 1.0, 7)
    seed_transaction(db, 3, item.id, "Yogurt", "sale", 1.0, 1.0, 5)
    seed_transaction(db, 3, item.id, "Yogurt", "disposal", 8.0, 1.0, 5)
    db.commit()
    result = classify_item(db, item, None)
    assert result["cause"] in ("expiry", "overstocking", "excess_purchasing")