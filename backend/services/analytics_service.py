"""Waste analytics aggregations for the dashboard and analytics API."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.inventory_item import InventoryItem
from models.transaction import Transaction
from models.risk_assessment import RiskAssessment
from models.waste_prediction import WastePrediction
from models.waste_cause import WasteCause
from services.forecasting import SALES_TYPES, WASTE_TYPES, DONATION_TYPES, PURCHASE_TYPES, utc_now
from services.forecast_evaluator import evaluate_tenant, tenant_headline

PERIOD_DAYS = {"day": 1, "week": 7, "month": 30}


def _sum_qty(db: Session, owner_id: int, tx_types, since) -> float:
    total = (
        db.query(func.coalesce(func.sum(Transaction.quantity), 0.0))
        .filter(
            Transaction.owner_id == owner_id,
            Transaction.transaction_type.in_(tx_types),
            Transaction.transaction_date >= since,
        )
        .scalar()
    )
    return float(total or 0.0)


def _sum_value(db: Session, owner_id: int, tx_types, since) -> float:
    rows = (
        db.query(Transaction.quantity, Transaction.unit_price)
        .filter(
            Transaction.owner_id == owner_id,
            Transaction.transaction_type.in_(tx_types),
            Transaction.transaction_date >= since,
        )
        .all()
    )
    return sum((q or 0.0) * (p or 0.0) for q, p in rows)


def current_risk_counts(db: Session, owner_id: int) -> dict:
    rows = (
        db.query(RiskAssessment.risk_level, func.count(RiskAssessment.id))
        .filter(RiskAssessment.owner_id == owner_id)
        .group_by(RiskAssessment.risk_level)
        .all()
    )
    counts = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for level, count in rows:
        counts[level] = counts.get(level, 0) + count
    return counts


def predicted_waste(db: Session, owner_id: int, horizon_days: int = 7) -> dict:
    preds = (
        db.query(WastePrediction)
        .filter(WastePrediction.owner_id == owner_id)
        .all()
    )
    total_waste = 0.0
    total_value = 0.0
    total_surplus = 0.0
    rows = 0
    seen = set()
    # surplus for the whole horizon == row with the furthest target date per item
    for p in preds:
        if p.item_id not in seen:
            seen.add(p.item_id)
            rows += 1
    max_date_per_item: dict[int, tuple] = {}
    for p in preds:
        cur = max_date_per_item.get(p.item_id)
        if cur is None or p.target_date > cur[0]:
            max_date_per_item[p.item_id] = (p.target_date, p.predicted_surplus or 0.0, p.predicted_waste or 0.0, p.expected_waste_value or 0.0)
    for _, (_, surplus, waste, value) in max_date_per_item.items():
        total_surplus += surplus
        total_waste += waste
        total_value += value
    return {
        "total_waste": round(total_waste, 2),
        "total_value": round(total_value, 2),
        "total_surplus": round(total_surplus, 2),
        "items_covered": rows,
    }


def analytics(db: Session, owner_id: int, period: str = "week") -> dict:
    days = PERIOD_DAYS.get(period, 7)
    since = utc_now() - timedelta(days=days)

    items = db.query(InventoryItem).filter(InventoryItem.owner_id == owner_id).all()
    total_units = sum(i.quantity or 0.0 for i in items)
    total_value = sum((i.quantity or 0.0) * (i.cost_per_unit or 0.0) for i in items)

    sales = _sum_qty(db, owner_id, SALES_TYPES, since)
    waste = _sum_qty(db, owner_id, WASTE_TYPES, since)
    donations = _sum_qty(db, owner_id, DONATION_TYPES, since)
    purchases = _sum_qty(db, owner_id, PURCHASE_TYPES, since)
    waste_value = _sum_value(db, owner_id, WASTE_TYPES, since)
    donation_value = _sum_value(db, owner_id, DONATION_TYPES, since)

    waste_pct = (waste / (sales + waste) * 100) if (sales + waste) > 0 else 0.0

    # waste by category
    from models.category import Category
    categories = {c.id: c for c in db.query(Category).filter(Category.owner_id == owner_id).all()}

    tx_waste = (
        db.query(Transaction)
        .filter(Transaction.owner_id == owner_id, Transaction.transaction_type == "disposal", Transaction.transaction_date >= since)
        .all()
    )
    item_id_to_cat = {i.id: i.category_id for i in items}
    waste_by_category: dict[str, dict] = {}
    top_products: dict[tuple, dict] = {}
    for tx in tx_waste:
        cat_id = item_id_to_cat.get(tx.item_id)
        cat_name = categories[cat_id].name if cat_id in categories else "Uncategorized"
        entry = waste_by_category.setdefault(cat_name, {"quantity": 0.0, "value": 0.0})
        entry["quantity"] += tx.quantity or 0.0
        entry["value"] += (tx.quantity or 0.0) * (tx.unit_price or 0.0) or 0.0
        pkey = (tx.item_id, tx.item_name)
        p = top_products.setdefault(pkey, {"quantity": 0.0, "value": 0.0})
        p["quantity"] += tx.quantity or 0.0
        p["value"] += (tx.quantity or 0.0) * (tx.unit_price or 0.0) or 0.0

    pred = predicted_waste(db, owner_id, horizon_days=7)
    risk_counts = current_risk_counts(db, owner_id)

    # expiring count (0-7 days)
    expiring = 0
    from services.risk_service import days_to_expiry, expiration_status
    for i in items:
        if expiration_status(days_to_expiry(i.expiry_date)) in ("expired", "expiring_soon", "expiring"):
            expiring += 1

    causes_rows = db.query(WasteCause).filter(WasteCause.owner_id == owner_id).all()
    causes_count: dict[str, int] = {}
    for c in causes_rows:
        causes_count[c.cause] = causes_count.get(c.cause, 0) + 1

    forecast = tenant_headline(db, owner_id)

    return {
        "period": period,
        "kpis": {
            "total_items": len(items),
            "total_units": round(total_units, 2),
            "total_value": round(total_value, 2),
            "sales": round(sales, 2),
            "purchases": round(purchases, 2),
            "waste_qty": round(waste, 2),
            "waste_value": round(waste_value, 2),
            "waste_pct": round(waste_pct, 2),
            "donations": round(donations, 2),
            "donation_value": round(donation_value, 2),
            "expiring_items": expiring,
            "high_risk_items": risk_counts.get("high", 0) + risk_counts.get("critical", 0),
            "critical_items": risk_counts.get("critical", 0),
            "predicted_waste": pred["total_waste"],
            "predicted_waste_value": pred["total_value"],
            "predicted_surplus": pred["total_surplus"],
        },
        "risk_counts": risk_counts,
        "waste_by_category": [
            {"category": name, "quantity": round(e["quantity"], 2), "value": round(e["value"], 2)}
            for name, e in waste_by_category.items()
        ],
        "top_waste_products": [
            {"item_id": k[0], "item_name": k[1], "quantity": round(v["quantity"], 2), "value": round(v["value"], 2)}
            for k, v in sorted(top_products.items(), key=lambda kv: kv[1]["quantity"], reverse=True)[:10]
        ],
        "waste_causes": [{"cause": k, "count": v} for k, v in causes_count.items()],
        "forecast_accuracy": forecast,
        "donation_trend": {"quantity": round(donations, 2), "value": round(donation_value, 2)},
    }


def trends(db: Session, owner_id: int, days: int = 30) -> list[dict]:
    """Daily time series for charts: sales, waste, waste value, donations, purchases."""
    since = utc_now() - timedelta(days=days)
    rows = (
        db.query(Transaction)
        .filter(Transaction.owner_id == owner_id, Transaction.transaction_date >= since)
        .all()
    )
    buckets: dict[datetime, dict] = {}
    for tx in rows:
        day = (tx.transaction_date or utc_now()).replace(hour=0, minute=0, second=0, microsecond=0)
        b = buckets.setdefault(day, {"sales": 0.0, "waste": 0.0, "waste_value": 0.0, "donations": 0.0, "purchases": 0.0})
        q = tx.quantity or 0.0
        if tx.transaction_type == "sale":
            b["sales"] += q
        elif tx.transaction_type == "disposal":
            b["waste"] += q
            b["waste_value"] += q * (tx.unit_price or 0.0)
        elif tx.transaction_type == "donation":
            b["donations"] += q
        elif tx.transaction_type == "purchase":
            b["purchases"] += q

    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        b = buckets.get(day, {})
        out.append({
            "date": day.strftime("%Y-%m-%d"),
            "sales": round(b.get("sales", 0.0), 2),
            "waste": round(b.get("waste", 0.0), 2),
            "waste_value": round(b.get("waste_value", 0.0), 2),
            "donations": round(b.get("donations", 0.0), 2),
            "purchases": round(b.get("purchases", 0.0), 2),
        })
    return out


def forecast_vs_actual_series(db: Session, owner_id: int, days: int = 30) -> dict:
    """Predicted vs actual daily demand (and waste) over the window."""
    since = utc_now() - timedelta(days=days)
    preds = (
        db.query(WastePrediction)
        .filter(WastePrediction.owner_id == owner_id, WastePrediction.target_date >= since)
        .all()
    )
    pred_by_day: dict[str, dict] = {}
    for p in preds:
        key = p.target_date.strftime("%Y-%m-%d")
        b = pred_by_day.setdefault(key, {"demand": 0.0, "waste": 0.0})
        b["demand"] += p.predicted_demand or 0.0
        b["waste"] += p.predicted_waste or 0.0

    actual_rows = (
        db.query(Transaction)
        .filter(Transaction.owner_id == owner_id, Transaction.transaction_date >= since)
        .all()
    )
    act_by_day: dict[str, dict] = {}
    for tx in actual_rows:
        key = (tx.transaction_date or utc_now()).strftime("%Y-%m-%d")
        b = act_by_day.setdefault(key, {"demand": 0.0, "waste": 0.0})
        if tx.transaction_type == "sale":
            b["demand"] += tx.quantity or 0.0
        elif tx.transaction_type == "disposal":
            b["waste"] += tx.quantity or 0.0

    days_list = sorted(set(list(pred_by_day.keys()) + list(act_by_day.keys())))
    out = []
    for d in days_list:
        p = pred_by_day.get(d, {})
        a = act_by_day.get(d, {})
        out.append({
            "date": d,
            "predicted_demand": round(p.get("demand", 0.0), 2),
            "actual_demand": round(a.get("demand", 0.0), 2),
            "predicted_waste": round(p.get("waste", 0.0), 2),
            "actual_waste": round(a.get("waste", 0.0), 2),
        })
    return {"series": out}