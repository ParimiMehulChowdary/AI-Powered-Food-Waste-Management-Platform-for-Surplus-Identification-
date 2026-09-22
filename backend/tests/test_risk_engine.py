from services.risk_engine import classify, thresholds
from services import risk_engine


def test_classify_four_levels_against_configured_thresholds():
    t_low, t_mod, t_high = thresholds()
    # bands are exclusive on the upper edge (> boundary -> next level)
    assert classify(t_low - 1) == "low"
    assert classify(t_low) == "low"
    assert classify(t_low + 1) == "moderate"
    assert classify(t_mod) == "moderate"
    assert classify(t_mod + 1) == "high"
    assert classify(t_high) == "high"
    assert classify(t_high + 1) == "critical"
    assert classify(0) == "low"


def test_classify_extremes():
    assert classify(-5) == "low"
    assert classify(101) == "critical"


def test_assess_item_produces_explained_score(db):
    from models.inventory_item import InventoryItem
    item = InventoryItem(
        owner_id=1, name="Milk", quantity=80, unit="L",
        cost_per_unit=1.5, storage_location="Chiller",
        supplier="Dairy Co",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # no transaction history -> transparent fallback forecast, still assessed
    result = risk_engine.assess_item(db, item, category=None, forecast=None)

    assert 0.0 <= result["risk_score"] <= 100.0
    assert result["risk_level"] in ("low", "moderate", "high", "critical")
    assert isinstance(result["explanation"], str) and len(result["explanation"]) > 0
    assert len(result["factors"]) > 0
    # explanation must reference the actual product state
    assert "Milk" in result["item_name"]
    assert result["model_name"] == "risk_engine_v2"