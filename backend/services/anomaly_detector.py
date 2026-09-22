"""Anomaly detection for sales, inventory and waste series.

Uses rolling z-score on daily series when enough history exists (>7 points)
and IQR as a fallback. Every anomaly is explainable: detected value, expected
range and a human readable reason are all recorded.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.transaction import Transaction
from models.inventory_item import InventoryItem
from services.forecasting import daily_series, fill_gaps, SALES_TYPES, WASTE_TYPES, PURCHASE_TYPES, utc_now

Z_SCORE_WINDOW = 7
Z_THRESHOLD = 3.0
MIN_ROLLING_POINTS = Z_SCORE_WINDOW + 1
MIN_IQR_POINTS = 5


def _stats(values: list[float]) -> dict | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)
    return {"mean": mean, "std": std, "min": min(vals), "max": max(vals), "last": vals[-1], "prev_avg": sum(vals[:-1]) / (len(vals) - 1) if len(vals) > 1 else 0.0}


def _iqr_bounds(values: list[float]) -> tuple[float, float] | None:
    vals = sorted(values)
    if len(vals) < MIN_IQR_POINTS:
        return None
    q1 = vals[len(vals) // 4]
    q3 = vals[int(len(vals) * 3 / 4)]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return (lower, upper)


def _severity(z: float) -> str:
    if z >= 5:
        return "critical"
    if z >= 4:
        return "high"
    return "medium"


class AnomalyInfo:
    def __init__(self, anomaly_type: str, detected_value: float, expected: float, low, high, explanation: str, method: str, severity: str):
        self.anomaly_type = anomaly_type
        self.detected_value = round(detected_value, 3)
        self.expected_value = round(expected, 3)
        self.expected_low = round(low, 3) if low is not None else None
        self.expected_high = round(high, 3) if high is not None else None
        self.explanation = explanation
        self.method = method
        self.severity = severity

    def to_dict(self, owner_id: int, item_id: int | None, item_name: str | None, date_key: str) -> dict:
        return {
            "owner_id": owner_id,
            "item_id": item_id,
            "item_name": item_name,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "detected_value": self.detected_value,
            "expected_value": self.expected_value,
            "expected_low": self.expected_low,
            "expected_high": self.expected_high,
            "explanation": self.explanation,
            "method": self.method,
            "dedupe_key": f"{owner_id}:{self.anomaly_type}:{item_id or 0}:{date_key}",
        }


def _check_series(values_normalised: list[float], anomaly_type: str, owner_id: int, item_id: int | None, item_name: str | None, date_key: str) -> AnomalyInfo | None:
    total = len(values_normalised)
    if total < Z_SCORE_WINDOW:
        return None  # insufficient data: be conservative, do not fabricate

    stats = _stats(values_normalised)
    std = stats["std"]
    last = values_normalised[-1]
    want_high = anomaly_type in ("sales_spike", "demand_spike", "waste_spike", "product_waste_spike", "stock_increase")

    if std > 0:
        z = (last - stats["mean"]) / std
        if abs(z) >= Z_THRESHOLD:
            direction = "higher" if z > 0 else "lower"
            bounds = (stats["mean"] - Z_THRESHOLD * std, stats["mean"] + Z_THRESHOLD * std)
            expected = stats["mean"]
            exp_words = "demand/sales" if "demand" in anomaly_type or "sales" in anomaly_type else ("waste" if "waste" in anomaly_type else "stock")
            explanation = (
                f"{exp_words} today ({last:g}) is {abs(z):.1f} standard deviations {direction} than the "
                f"7-day rolling mean ({expected:g}). Expected range {bounds[0]:g}–{bounds[1]:g}."
            )
            return AnomalyInfo(anomaly_type, last, expected, bounds[0], bounds[1], explanation, "rolling_zscore", _severity(abs(z)))

    # IQR fallback when z-score has no spread
    bounds = _iqr_bounds(values_normalised)
    if bounds:
        lo, hi = bounds
        anchor = lo if want_high else hi
        if (want_high and last > hi) or (not want_high and last < lo):
            expected = stats["mean"]
            explanation = (
                f"Value {last:g} falls outside the IQR expected range {lo:g}–{hi:g} "
                f"(threshold-based)."
            )
            return AnomalyInfo(anomaly_type, last, expected, lo, hi, explanation, "iqr", _severity(abs(last - expected) / max(std, 1e-9) if std else 3))

    # literal rule: a non-zero value where history is all zero is unusual
    if all(v == 0 for v in values_normalised[:-1]) and last > 0:
        explanation = f"Value {last:g} appears while the entire observed history is zero."
        return AnomalyInfo(anomaly_type, last, 0.0, 0.0, 0.0, explanation, "rule_based", "low")
    return None


def detect_item_anomalies(db: Session, item: InventoryItem, date_key: str) -> list[dict]:
    owner = item.owner_id
    name = item.name
    results: list[dict] = []

    sales_series = [v for _, v in fill_gaps(daily_series(db, owner, item.id, SALES_TYPES, days=30), 30)]
    waste_series = [v for _, v in fill_gaps(daily_series(db, owner, item.id, WASTE_TYPES, days=30), 30)]
    purchase_series = [v for _, v in fill_gaps(daily_series(db, owner, item.id, PURCHASE_TYPES, days=30), 30)]

    sales_check = _check_series(sales_series, "sales_spike", owner, item.id, name, date_key)
    if sales_check:
        results.append(sales_check.to_dict(owner, item.id, name, date_key))
        drop = _check_series([-v for v in sales_series], "sales_drop", owner, item.id, name, date_key)
        if drop:
            drop.anomaly_type = "sales_drop"
            results.append(drop.to_dict(owner, item.id, name, date_key))

    waste_check = _check_series(waste_series, "product_waste_spike", owner, item.id, name, date_key)
    if waste_check:
        results.append(waste_check.to_dict(owner, item.id, name, date_key))

    stock_check = _check_series(purchase_series, "stock_increase", owner, item.id, name, date_key)
    if stock_check:
        results.append(stock_check.to_dict(owner, item.id, name, date_key))

    # stock accumulation: quantity far above typical
    if item.quantity and item.quantity > 0:
        stats = _stats(sales_series)
        if stats and stats["mean"] > 0 and stats["std"] > 0:
            z = (item.quantity - stats["mean"]) / stats["std"]
            if z >= 4:
                low, high = (stats["mean"] - 4 * stats["std"], stats["mean"] + 4 * stats["std"])
                results.append(AnomalyInfo(
                    "stock_accumulation", item.quantity, stats["mean"], low, high,
                    f"Stock level {item.quantity:g} units is {z:.1f}σ above the observed sales baseline ({stats['mean']:g} units/day). Possible overstocking.",
                    "rolling_zscore", _severity(z),
                ).to_dict(owner, item.id, name, date_key))

    return results


def _tenant_daily(db: Session, owner_id: int, tx_types, days: int = 30) -> list[float]:
    since = utc_now() - timedelta(days=days)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.owner_id == owner_id,
            Transaction.transaction_type.in_(tx_types),
            Transaction.transaction_date >= since,
        )
        .all()
    )
    buckets: dict[datetime, float] = {}
    for tx in rows:
        day = (tx.transaction_date or utc_now()).replace(hour=0, minute=0, second=0, microsecond=0)
        buckets[day] = buckets.get(day, 0.0) + (tx.quantity or 0.0)
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for offset in range(days - 1, -1, -1):
        out.append(buckets.get(today - timedelta(days=offset), 0.0))
    return out


def detect_tenant_anomalies(db: Session, owner_id: int, date_key: str) -> list[dict]:
    """Tenant-level sales (demand) and waste anomalies across all products."""
    results: list[dict] = []
    all_sales = _tenant_daily(db, owner_id, SALES_TYPES)
    all_waste = _tenant_daily(db, owner_id, WASTE_TYPES)

    if sum(all_sales) > 0:
        spike = _check_series(all_sales, "demand_spike", owner_id, None, None, date_key)
        if spike:
            results.append(spike.to_dict(owner_id, None, None, date_key))
        drop = _check_series([-v for v in all_sales], "demand_drop", owner_id, None, None, date_key)
        if drop:
            drop.anomaly_type = "demand_drop"
            results.append(drop.to_dict(owner_id, None, None, date_key))

    if sum(all_waste) > 0:
        check = _check_series(all_waste, "waste_spike", owner_id, None, None, date_key)
        if check:
            results.append(check.to_dict(owner_id, None, None, date_key))

    return results


def exception_safe_detect(db: Session, owner_id: int, date_key: str) -> list[dict]:
    """Run detection across all tenant items, never raising on bad data."""
    items = db.query(InventoryItem).filter(InventoryItem.owner_id == owner_id).all()
    out: list[dict] = []
    for item in items:
        try:
            out.extend(detect_item_anomalies(db, item, date_key))
        except Exception:  # noqa: BLE001 - anomaly detection must never block the job
            continue
    try:
        out.extend(detect_tenant_anomalies(db, owner_id, date_key))
    except Exception:  # noqa: BLE001
        pass
    return out