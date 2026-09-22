"""Explainable waste-risk engine (Milestone 2).

Builds a 0-100 risk score per product from transparent, configurable factors
and produces a plain-language explanation generated from the actual data.

The Milestone 1 risk scoring (``services/risk_service.py``) is left untouched;
this engine re-uses its day-count helper and adds forecasting-aware factors.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from config import settings
from models.inventory_item import InventoryItem
from services.risk_service import days_to_expiry

MODEL_NAME = "risk_engine_v2"
MODEL_VERSION = "2.0.0"

# Contribution weights (configurable per installation).
W_DEFAULT = {
    "expiry": 1.0,
    "stock_demand": 1.0,
    "waste_rate": 1.0,
    "sales_trend": 1.0,
    "perishability": 1.0,
    "storage": 1.0,
    "stock_age": 1.0,
}


def thresholds() -> tuple[int, int, int]:
    raw = getattr(settings, "RISK_THRESHOLDS", "35,60,80")
    try:
        parts = [int(x.strip()) for x in str(raw).split(",")]
        return (parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        return (35, 60, 80)


def classify(score: float) -> str:
    t_low, t_mod, t_high = thresholds()
    if score > t_high:
        return "critical"
    if score > t_mod:
        return "high"
    if score > t_low:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Factor computations (each returns (contribution 0-100, label, detail))
# ---------------------------------------------------------------------------
def _expiry_factor(days_left: int | None) -> tuple[float, str, str]:
    if days_left is None:
        return 5.0, "no expiry date", "No expiry date set; waste risk driven by stock levels."
    if days_left <= 0:
        return 40.0, f"expired {abs(days_left)} day(s) ago", "Item is past its expiry date."
    if days_left <= 2:
        return 34.0, f"{days_left} day(s) to expiry", "Very short remaining shelf life."
    if days_left <= 5:
        return 26.0, f"{days_left} day(s) to expiry", "Short remaining shelf life."
    if days_left <= 7:
        return 18.0, f"{days_left} day(s) to expiry", "Approaching expiry window."
    if days_left <= 14:
        return 10.0, f"{days_left} day(s) to expiry", "Moderate remaining shelf life."
    return 3.0, f"{days_left} day(s) to expiry", "Plenty of shelf life remaining."


def _stock_demand_factor(stock: float, daily_demand: float) -> tuple[float, str, str]:
    if daily_demand <= 0:
        if stock > 0:
            return 15.0, "no forecast demand", "No historical sales to clear current stock."
        return 0.0, "no stock", "No stock on hand."
    ratio = stock / daily_demand
    if ratio >= 3:
        contrib = 20.0
        label = f"stock is {ratio:.1f}x daily demand"
    elif ratio >= 2:
        contrib = 15.0
        label = f"stock is {ratio:.1f}x daily demand"
    elif ratio >= 1:
        contrib = 8.0
        label = f"stock is {ratio:.1f}x daily demand"
    elif ratio >= 0.5:
        contrib = 4.0
        label = f"stock covers ~{ratio:.1f} days of demand"
    else:
        contrib = 2.0
        label = f"stock is low relative to demand ({ratio:.2f}x)"
    return contrib, label, f"{stock:g} units in stock vs {daily_demand:g} units/day forecast demand."


def _waste_rate_factor(total_sales: float, total_waste: float) -> tuple[float, str, str]:
    turnover = total_sales + total_waste
    if turnover <= 0:
        return 0.0, "no waste history", "No sales or disposal history in the last 30 days."
    rate = total_waste / turnover * 100
    contrib = max(0.0, min(20.0, rate * 0.5))
    return contrib, f"historical waste rate {rate:.0f}%", f"{total_waste:g} units wasted out of {turnover:g} units moved."


def _sales_trend_factor(recent_avg: float, previous_avg: float) -> tuple[float, str, str]:
    if previous_avg <= 0:
        return 0.0, "insufficient sales trend", "Not enough sales history to compare trends."
    delta_pct = (recent_avg - previous_avg) / previous_avg * 100
    if delta_pct >= 0:
        return 0.0, f"recent sales up {delta_pct:.0f}%", "Demand is growing; stock is clearing."
    contrib = max(0.0, min(15.0, -delta_pct * 0.15))
    return contrib, f"recent sales down {-delta_pct:.0f}%", f"Recent demand dropped {-delta_pct:.0f}% vs the prior period."


def _perishability_factor(risk: str) -> tuple[float, str, str]:
    return {"low": (0.0, "low perishability", ""), "medium": (5.0, "medium perishability", ""), "high": (10.0, "high perishability", "")}.get(risk, (5.0, "unknown perishability", ""))


def _storage_factor(storage: str) -> tuple[float, str, str]:
    return {"frozen": (0.0, "frozen storage", ""), "chilled": (4.0, "chilled storage", ""), "ambient": (8.0, "ambient storage", "")}.get(storage, (8.0, "ambient storage", ""))


def _stock_age_factor(days_in_stock: int | None, shelf_life_days: int | None) -> tuple[float, str, str]:
    if days_in_stock is None:
        return 2.0, "stock age unknown", ""
    if shelf_life_days and shelf_life_days > 0:
        ratio = days_in_stock / shelf_life_days
        if ratio >= 1:
            return 9.0, f"in stock {days_in_stock} days (≥ {shelf_life_days}d shelf life)", "Stock held longer than the category shelf life."
        if ratio >= 0.75:
            return 6.0, f"in stock {days_in_stock} of {shelf_life_days}d shelf life", "Stock age close to category shelf life."
        return 2.0, f"held {days_in_stock} days", ""
    if days_in_stock >= 14:
        return 4.0, f"held {days_in_stock} days", "No shelf-life reference; item held a long time without movement."
    return 2.0, f"held {days_in_stock} days", ""


def _multiplicative_scale(perishability: str, waste_risk_weight: float) -> float:
    # re-use M1 category weight to keep scores consistent with M1 behaviour
    p = 1.0 if perishability == "high" else (0.9 if perishability == "medium" else 0.8)
    return p * (waste_risk_weight or 1.0)


def assess_item(
    db: Session,
    item: InventoryItem,
    category=None,
    forecast: dict | None = None,
) -> dict:
    """Compute a full explainable assessment for one item.

    ``forecast`` is the dict produced by ``forecasting.forecast_item``; when it
    is not provided a statistical fallback is computed from transaction history.
    """
    from services.forecasting import forecast_item

    if forecast is None:
        forecast = forecast_item(db, item, horizon_days=7)

    stock = item.quantity or 0.0
    days_left = days_to_expiry(item.expiry_date) if item.expiry_date else None
    perishability = (category.perishability_risk if category else None) or "medium"
    storage = (category.storage_requirement if category else None) or "ambient"
    shelf_life = category.default_shelf_life_days if category and category.default_shelf_life_days else None

    days_in_stock = None
    if item.created_at:
        days_in_stock = (datetime.utcnow() - item.created_at.replace(tzinfo=None)).days

    contributions: list[tuple[str, float, str, str]] = []
    c, label, detail = _expiry_factor(days_left)
    contributions.append(("expiry", c, label, detail))
    daily_demand = forecast["total_demand"] / max(forecast["horizon_days"], 1)
    c, label, detail = _stock_demand_factor(stock, daily_demand)
    contributions.append(("stock_vs_demand", c, label, detail))
    c, label, detail = _waste_rate_factor(
        forecast["history"].get("total_sales_30d", 0.0),
        forecast["history"].get("total_waste_30d", 0.0),
    )
    contributions.append(("waste_rate", c, label, detail))

    # recent vs previous 7-day sales trend
    from services.forecasting import daily_series, SALES_TYPES
    series = {k: v for k, v in daily_series(db, item.owner_id, item.id, SALES_TYPES, days=60).items()}
    now_d = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    recent = sum(v for d, v in series.items() if d >= now_d - timedelta(days=7))
    previous = sum(v for d, v in series.items() if now_d - timedelta(days=14) <= d < now_d - timedelta(days=7))
    c, label, detail = _sales_trend_factor(recent / 7.0, previous / 7.0)
    contributions.append(("sales_trend", c, label, detail))

    c, label, detail = _perishability_factor(perishability)
    contributions.append(("perishability", c, label, detail))
    c, label, detail = _storage_factor(storage)
    contributions.append(("storage", c, label, detail))
    c, label, detail = _stock_age_factor(days_in_stock, shelf_life)
    contributions.append(("stock_age", c, label, detail))

    weights = W_DEFAULT
    raw = sum(c * weights.get(name, 1.0) for name, c, _, _ in contributions)
    scale = _multiplicative_scale(perishability, category.waste_risk_weight if category else 1.0)
    score = round(min(100.0, raw * scale), 1)
    level = classify(score)

    factor_list = [
        {"factor": name, "value": label, "detail": detail}
        for name, _, label, detail in contributions
        if label
    ]

    explanation = build_explanation(level, score, factor_list, contributions, stock, daily_demand, days_left)

    return {
        "item_id": item.id,
        "item_name": item.name,
        "category_id": item.category_id,
        "owner_id": item.owner_id,
        "risk_score": score,
        "risk_level": level,
        "factors": factor_list,
        "explanation": explanation,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "thresholds": {"low_max": thresholds()[0], "moderate_max": thresholds()[1], "high_max": thresholds()[2]},
        "stock": stock,
        "daily_demand": round(daily_demand, 3),
        "days_to_expiry": days_left,
    }


def build_explanation(level: str, score: float, factors: list[dict], contributions, stock: float, daily_demand: float, days_left: int | None) -> str:
    level_display = level.capitalize()
    reason_parts = []
    factor_detail = {name: (label, detail) for name, _, label, detail in contributions}

    if days_left is not None:
        if days_left <= 0:
            reason_parts.append(f"it expired {abs(days_left)} day(s) ago")
        elif days_left <= 2:
            reason_parts.append(f"only {days_left} day(s) remain before expiry")
    if stock > 0 and daily_demand > 0:
        ratio = stock / daily_demand
        if ratio >= 1:
            reason_parts.append(f"{stock:g} units are in stock, {ratio:.1f}x forecast demand")
    waste_rate_label, _ = factor_detail.get("waste_rate", (None, None))
    if waste_rate_label and "no waste history" not in waste_rate_label and "no sales" not in waste_rate_label:
        reason_parts.append(f"historical waste rate is {waste_rate_label.split()[-1]}")
    trend_label, _ = factor_detail.get("sales_trend", (None, None))
    if trend_label and "insufficient" not in trend_label:
        reason_parts.append(trend_label)

    if not reason_parts:
        return f"{level_display} waste risk score {score:.0f}. No dominant risk factors identified."
    return f"{level_display} waste risk because {'; '.join(reason_parts)}."