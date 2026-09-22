"""Time-series demand / waste forecasting with transparent fallbacks.

Milestone 1 had no forecasting implementation; this module provides a
lightweight, dependency-free statistical layer (exponential smoothing,
moving average, linear trend) that is safe to run on small histories and
clearly falls back to a rule-based estimate when data is insufficient.

Model training is separated from inference: nothing here is retrained on
API reads. The scheduled jobs call ``generate_predictions`` and persist the
output; API endpoints only read from the database.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.transaction import Transaction
from models.inventory_item import InventoryItem
from config import settings

logger = logging.getLogger("forecasting")

MODEL_VERSION = "1.0.0"
MIN_POINTS_FOR_ML = 3
DEFAULT_HORIZON_DAYS = 7
EXPIRY_BOOST_WINDOW_DAYS = 3

SALES_TYPES = ("sale",)
WASTE_TYPES = ("disposal",)
DONATION_TYPES = ("donation",)
PURCHASE_TYPES = ("purchase",)


def utc_now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Series extraction
# ---------------------------------------------------------------------------
def daily_series(db: Session, owner_id: int, item_id: int, tx_types, days: int = 60) -> dict[datetime, float]:
    """Aggregate transaction quantities per UTC day for the given types."""
    since = utc_now() - timedelta(days=days)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.owner_id == owner_id,
            Transaction.item_id == item_id,
            Transaction.transaction_type.in_(tx_types),
            Transaction.transaction_date >= since,
        )
        .all()
    )
    out: dict[datetime, float] = {}
    for tx in rows:
        day = (tx.transaction_date or utc_now()).replace(hour=0, minute=0, second=0, microsecond=0)
        out[day] = out.get(day, 0.0) + (tx.quantity or 0.0)
    return out


def fill_gaps(series: dict[datetime, float], days: int = 30) -> list[tuple[datetime, float]]:
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    filled = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        filled.append((day, series.get(day, 0.0)))
    return filled


def last_mean(series: dict[datetime, float], days: int = 7) -> float:
    tail = fill_gaps(series, days)
    values = [v for _, v in tail]
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Statistical methods (pure python)
# ---------------------------------------------------------------------------
def exponential_smoothing(values: list[float], alpha: float = 0.3) -> float:
    if not values:
        return 0.0
    level = values[0]
    for v in values[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def moving_average(values: list[float], window: int = 7) -> float:
    if not values:
        return 0.0
    window = max(1, min(window, len(values)))
    return sum(values[-window:]) / window


def linear_trend(values: list[float]) -> float:
    """Least-squares linear trend extrapolated one step ahead."""
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return values[0]
    xs = list(range(n))
    xmean = sum(xs) / n
    ymean = sum(values) / n
    num = sum((x - xmean) * (y - ymean) for x, y in zip(xs, values))
    den = sum((x - xmean) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = ymean - slope * xmean
    return max(0.0, slope * n + intercept)


def coeff_of_variation(values: list[float]) -> float:
    mean = sum(values) / len(values) if values else 0.0
    if mean <= 0:
        return 1.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / mean


def choose_method(values: list[float]) -> str:
    if len(values) < MIN_POINTS_FOR_ML:
        return "fallback"
    trend_ratio = abs(linear_trend(values) - last_mean_from(values)) / max(last_mean_from(values), 1e-9)
    if len(values) >= 10 and trend_ratio > 0.5:
        return "linear_trend"
    if coeff_of_variation(values) < 0.4 and len(values) >= 7:
        return "moving_average"
    return "exp_smoothing"


def last_mean_from(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def predict_next(values: list[float], method: str) -> float:
    if method == "linear_trend":
        return linear_trend(values)
    if method == "moving_average":
        return moving_average(values, window=7)
    return exponential_smoothing(values)


def confidence_from(values: list[float], method: str) -> float:
    if not values:
        return 0.0
    n = len(values)
    data_conf = min(1.0, n / 14.0)
    stability = 1.0 - min(1.0, coeff_of_variation(values))
    model_conf = 1.0 if method != "fallback" else 0.0
    return round(max(0.0, 0.5 * data_conf + 0.3 * stability + 0.2 * model_conf), 3)


# ---------------------------------------------------------------------------
# Forecasting API
# ---------------------------------------------------------------------------
def forecast_kind(db: Session, owner_id: int, item_id: int, tx_types, days: int = 60) -> dict:
    """Return a model-free daily forecast for a single signal type."""
    series = daily_series(db, owner_id, item_id, tx_types, days=days)
    values = [v for _, v in fill_gaps(series, days=min(days, 30))]
    if not any(values):
        # no signal at all -> never claim model accuracy on hallucinated data
        return {
            "method": "fallback",
            "model_name": "rule_based_fallback",
            "model_version": MODEL_VERSION,
            "is_fallback": True,
            "confidence": 0.0,
            "daily_value": 0.0,
            "points": 0,
        }
    method = choose_method(values)
    if method == "fallback":
        level = last_mean(series, days=11)
        return {
            "method": "fallback",
            "model_name": "rule_based_fallback",
            "model_version": MODEL_VERSION,
            "is_fallback": True,
            "confidence": 0.0,
            "daily_value": round(max(level, 0.0), 3),
            "points": sum(1 for v in values if v > 0),
        }
    prediction = predict_next(values, method)
    return {
        "method": method,
        "model_name": f"{method}_forecast_v1",
        "model_version": MODEL_VERSION,
        "is_fallback": False,
        "confidence": confidence_from(values, method),
        "daily_value": round(max(prediction, 0.0), 3),
        "points": sum(1 for v in values if v > 0),
    }


def risk_level_from_probability(prob: float) -> str:
    """4-level label from a 0-1 waste probability using configured thresholds."""
    thresholds = _thresholds()
    pct = prob * 100
    if pct > thresholds[2]:
        return "critical"
    if pct > thresholds[1]:
        return "high"
    if pct > thresholds[0]:
        return "moderate"
    return "low"


def _thresholds() -> tuple[int, int, int]:
    raw = getattr(settings, "RISK_THRESHOLDS", "35,60,80")
    try:
        parts = [int(x.strip()) for x in str(raw).split(",")]
        return (parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        return (35, 60, 80)


def forecast_item(
    db: Session,
    item: InventoryItem,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> dict:
    """Forecast demand, waste and surplus for a single inventory item.

    Returns a dict with ``targets`` (one entry per target date), plus summary
    values. Never fabricates data: when history is absent it produces a
    transparent rule-based estimate (demand 0, surplus = stock).
    """
    owner_id = item.owner_id
    demand_fc = forecast_kind(db, owner_id, item.id, SALES_TYPES)
    waste_fc = forecast_kind(db, owner_id, item.id, WASTE_TYPES)
    purchase_fc = forecast_kind(db, owner_id, item.id, PURCHASE_TYPES)
    donation_fc = forecast_kind(db, owner_id, item.id, DONATION_TYPES)

    days_left = None
    if item.expiry_date:
        days_left = (item.expiry_date.replace(tzinfo=None) - utc_now()).days

    daily_demand = demand_fc["daily_value"]
    daily_waste = waste_fc["daily_value"]
    stock = item.quantity or 0.0
    cost = item.cost_per_unit or 0.0

    total_sales = sum(v for v in _sales_values(db, owner_id, item.id))
    total_waste = sum(v for v in _waste_values(db, owner_id, item.id))
    waste_probability = _waste_probability(total_sales, total_waste, days_left, demand_fc["is_fallback"])

    targets = []
    cumulative_demand = 0.0
    cumulative_waste = 0.0
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(1, horizon_days + 1):
        target = today + timedelta(days=offset)
        day_demand = round(daily_demand, 3)
        day_waste = round(daily_waste + day_demand * waste_probability, 3)
        cumulative_demand += day_demand
        cumulative_waste += day_waste
        remaining = max(round(stock - cumulative_demand, 3), 0.0)
        prob = min(1.0, waste_probability)
        targets.append({
            "target_date": target,
            "predicted_demand": day_demand,
            "predicted_sales": day_demand,
            "predicted_waste": day_waste,
            "predicted_surplus": remaining,
            "waste_probability": round(prob, 3),
            "waste_risk_level": risk_level_from_probability(prob),
            "expected_waste_value": round(day_waste * cost, 2),
            "expected_waste_pct": round(prob * 100, 1),
        })

    model_name = "combined" if not (demand_fc["is_fallback"] or waste_fc["is_fallback"]) else demand_fc["model_name"]
    is_fallback = demand_fc["is_fallback"] or waste_fc["is_fallback"]
    confidence = round((demand_fc["confidence"] + waste_fc["confidence"]) / 2, 3)

    total_demand = round(sum(t["predicted_demand"] for t in targets), 2)
    total_waste = round(sum(t["predicted_waste"] for t in targets), 2)
    return {
        "item_id": item.id,
        "item_name": item.name,
        "category_id": item.category_id,
        "horizon_days": horizon_days,
        "stock": stock,
        "cost_per_unit": cost,
        "days_to_expiry": days_left,
        "model_name": model_name,
        "model_version": MODEL_VERSION,
        "is_fallback": is_fallback,
        "confidence": confidence,
        "method": f"{demand_fc['method']}/waste:{waste_fc['method']}",
        "data_points": {"sales": demand_fc["points"], "waste": waste_fc["points"], "purchase": purchase_fc["points"], "donation": donation_fc["points"]},
        "history": {"total_sales_30d": total_sales, "total_waste_30d": total_waste},
        "total_demand": total_demand,
        "total_waste": total_waste,
        "total_waste_value": round(total_waste * cost, 2),
        "total_surplus": max(round(stock - total_demand, 2), 0.0),
        "waste_probability": round(waste_probability, 3),
        "targets": targets,
    }


def _sales_values(db: Session, owner_id: int, item_id: int) -> list[float]:
    series = daily_series(db, owner_id, item_id, SALES_TYPES, days=30)
    return [v for _, v in fill_gaps(series, days=30)]


def _waste_values(db: Session, owner_id: int, item_id: int) -> list[float]:
    series = daily_series(db, owner_id, item_id, WASTE_TYPES, days=30)
    return [v for _, v in fill_gaps(series, days=30)]


def _waste_probability(total_sales: float, total_waste: float, days_left: int | None, demand_fallback: bool) -> float:
    """0-1 probability of a unit being wasted.

    Uses historical waste rate when available; boosts towards 1 as expiry
    approaches (since forecasted demand may not clear stock).
    """
    baseline = 0.1
    turnover = total_sales + total_waste
    if turnover > 0:
        baseline = total_waste / turnover
    if demand_fallback and total_sales == 0:
        baseline = max(baseline, 0.2)
    if days_left is not None:
        if days_left <= 0:
            baseline = min(1.0, baseline + 0.6)
        elif days_left <= EXPIRY_BOOST_WINDOW_DAYS:
            baseline = min(1.0, baseline + (EXPIRY_BOOST_WINDOW_DAYS - days_left + 1) * 0.15)
    return max(0.0, min(1.0, baseline))


def generate_predictions_for_item(
    db: Session,
    item: InventoryItem,
    owner_id: int,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> tuple[list[dict], dict]:
    """Persist prediction rows for a single item; returns (rows, summary)."""
    result = forecast_item(db, item, horizon_days=horizon_days)
    from models.waste_prediction import WastePrediction

    # delete stale open predictions for this item so the latest target set wins
    db.query(WastePrediction).filter(
        WastePrediction.owner_id == owner_id,
        WastePrediction.item_id == item.id,
        WastePrediction.target_date >= utc_now().replace(hour=0, minute=0, second=0, microsecond=0),
    ).delete()

    rows = []
    for t in result["targets"]:
        row = WastePrediction(
            owner_id=owner_id,
            item_id=item.id,
            item_name=item.name,
            category_id=item.category_id,
            prediction_date=utc_now(),
            target_date=t["target_date"],
            predicted_demand=t["predicted_demand"],
            predicted_sales=t["predicted_sales"],
            predicted_surplus=t["predicted_surplus"],
            predicted_waste=t["predicted_waste"],
            waste_probability=t["waste_probability"],
            waste_risk_level=t["waste_risk_level"],
            expected_waste_value=t["expected_waste_value"],
            expected_waste_pct=t["expected_waste_pct"],
            confidence=result["confidence"],
            model_name=result["model_name"],
            model_version=result["model_version"],
            is_fallback=result["is_fallback"],
            method=result["method"],
        )
        db.add(row)
        rows.append(row)
    return rows, result