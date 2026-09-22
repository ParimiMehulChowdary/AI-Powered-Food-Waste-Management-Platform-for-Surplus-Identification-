from datetime import datetime, timedelta


PERISHABILITY_WEIGHT = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
}

STORAGE_WEIGHT = {
    "ambient": 1.2,
    "chilled": 1.0,
    "frozen": 0.7,
}


def days_to_expiry(expiry_date: datetime | None) -> int | None:
    if expiry_date is None:
        return None
    diff = expiry_date.replace(tzinfo=None) - datetime.utcnow().replace(tzinfo=None)
    return diff.days


def compute_risk_score(
    days_left: int | None,
    quantity: float,
    perishability_risk: str = "medium",
    storage_requirement: str = "ambient",
    waste_risk_weight: float = 1.0,
) -> float:
    """Waste risk scoring algorithm combining days-to-expiry, stock level and
    perishability/storage characteristics into an actionable 0-100 score."""
    score = 0.0

    if days_left is None:
        score += 10
    elif days_left <= 0:
        score += 50
    elif days_left <= 2:
        score += 45
    elif days_left <= 5:
        score += 35
    elif days_left <= 7:
        score += 25
    elif days_left <= 14:
        score += 15
    else:
        score += 5

    if quantity > 100:
        score += 20
    elif quantity > 50:
        score += 15
    elif quantity > 10:
        score += 10
    elif quantity > 0:
        score += 5
    else:
        score += 15

    score *= PERISHABILITY_WEIGHT.get(perishability_risk, 1.0)
    score *= STORAGE_WEIGHT.get(storage_requirement, 1.0)
    score *= waste_risk_weight

    return round(min(score, 100), 1)


def risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def expiration_status(days_left: int | None) -> str:
    if days_left is None:
        return "no_expiry"
    if days_left < 0:
        return "expired"
    if days_left <= 3:
        return "expiring_soon"
    if days_left <= 7:
        return "expiring"
    return "fresh"


def build_alert_message(item_name: str, status: str, days_left: int | None) -> str | None:
    if status == "expired":
        return f"'{item_name}' has expired and should be disposed or — if still safe — flagged for donation."
    if status == "expiring_soon":
        return f"'{item_name}' expires in {days_left} day(s). Consider promoting, donating, or discounting soon."
    if status == "expiring":
        return f"'{item_name}' will expire in {days_left} day(s)."
    return None


def build_shelf_life_breach_message(item_name: str, days_since_received: int, default_shelf_life: int) -> str:
    return f"'{item_name}' has been in inventory for {days_since_received} days, exceeding the category shelf life of {default_shelf_life} days. Review for donation or disposal."


def build_low_stock_message(item_name: str, current_quantity: float, threshold: float, unit: str) -> str:
    return f"'{item_name}' stock is low: {current_quantity} {unit} remaining (threshold: {threshold} {unit}). Consider reordering."
