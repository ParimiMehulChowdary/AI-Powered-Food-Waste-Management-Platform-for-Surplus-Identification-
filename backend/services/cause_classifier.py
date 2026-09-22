"""Waste cause classification.

A transparent, rule-based classifier instead of an unreliable ML model when
data is thin. Rules are derived from actual transaction history and, where
available, forecast accuracy for the item.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models.inventory_item import InventoryItem
from models.transaction import Transaction
from services.forecasting import daily_series, fill_gaps, SALES_TYPES, WASTE_TYPES, PURCHASE_TYPES

CAUSES = [
    "overstocking",
    "low_demand",
    "expiry",
    "poor_forecasting",
    "seasonal_demand_change",
    "excess_purchasing",
    "storage_issue",
    "product_damage",
    "operational_issue",
]


def classify_item(db: Session, item: InventoryItem, category=None) -> dict | None:
    """Return {cause, explanation, confidence} or None when no waste exists."""
    sales_series = daily_series(db, item.owner_id, item.id, SALES_TYPES, days=30)
    waste_series = daily_series(db, item.owner_id, item.id, WASTE_TYPES, days=30)
    purchase_series = daily_series(db, item.owner_id, item.id, PURCHASE_TYPES, days=30)

    total_sales = sum(sales_series.values())
    total_waste = sum(waste_series.values())
    total_purchase = sum(purchase_series.values())

    if total_waste <= 0:
        return None

    # find the day with peak waste and check proximity to expiry-matching purchase age
    peak_day, peak_waste = max(waste_series.items(), key=lambda kv: kv[1])

    seasonal_factor = _seasonal_flag(db, item, total_sales)
    forecast_err = _forecast_error_flag(db, item)

    scoreboard: list[tuple[str, float, str]] = []

    # 1) expiry: waste peak occurs while item was near its expiry date
    created = item.created_at.replace(tzinfo=None) if item.created_at else None
    expired_on_receipt = (
        created is not None
        and item.expiry_date is not None
        and item.expiry_date.replace(tzinfo=None) <= created
    )
    if item.expiry_date:
        # purchases shortly before a waste spike on a perishable item
        recent_purchases = sum(1 for day, q in purchase_series.items() if (peak_day - day).days <= 3 and q > 0)
        if recent_purchases > 0 or expired_on_receipt:
            scoreboard.append(("expiry", 0.9, f"Waste peaked ({peak_waste:g} units) near the item's expiry date with stock still on hand."))
        elif (
            created is not None
            and category
            and category.default_shelf_life_days
            and (datetime.utcnow() - created).days >= category.default_shelf_life_days
        ):
            scoreboard.append(("expiry", 0.8, f"Item held {(datetime.utcnow() - created).days} days, beyond its {category.default_shelf_life_days}-day shelf life."))

    # 2) overstocking / excess purchasing
    if total_purchase > 0 and total_sales > 0 and (total_purchase / total_sales) >= 1.5:
        scoreboard.append(("overstocking", 0.85, f"Purchased {total_purchase:g} units vs only {total_sales:g} units sold in the last 30 days."))
    elif total_purchase > 0 and total_sales == 0:
        scoreboard.append(("excess_purchasing", 0.8, f"{total_purchase:g} units purchased with no recorded sales; over-purchased without demand evidence."))

    # 3) low demand
    tail = [v for v in fill_gaps(sales_series, 30)][-1]
    if total_sales == 0:
        scoreboard.append(("low_demand", 0.7, "No sales recorded while waste occurred."))
    elif _recent_vs_prior(db, item) < 0.7:
        scoreboard.append(("low_demand", 0.6, "Recent sales declined more than 30% vs the prior period."))

    # 4) poor forecasting
    if forecast_err:
        scoreboard.append(("poor_forecasting", 0.7, forecast_err))

    # 5) seasonal
    if seasonal_factor:
        scoreboard.append(("seasonal_demand_change", 0.6, seasonal_factor))

    # 6) storage issue
    if category:
        storage = category.storage_requirement
        perishability = category.perishability_risk
        if perishability == "high" and storage in ("ambient",):
            scoreboard.append(("storage_issue", 0.7, "High-perishability item stored in ambient conditions; consider chilled storage."))

    if not scoreboard:
        scoreboard.append(("operational_issue", 0.5, "Waste recorded without a dominant pattern; review handling and ordering practices."))

    best = max(scoreboard, key=lambda s: s[1])
    return {"cause": best[0], "explanation": best[2], "confidence": round(best[1], 2)}


def _recent_vs_prior(db: Session, item: InventoryItem) -> float:
    series = daily_series(db, item.owner_id, item.id, SALES_TYPES, days=30)
    values = [v for _, v in fill_gaps(series, 30)]
    recent = sum(values[-7:])
    prior = sum(values[-14:-7])
    return recent / prior if prior > 0 else 1.0


def _seasonal_flag(db: Session, item: InventoryItem, total_sales: float) -> str | None:
    # compare recent 7d daily average to the same items 3-4 weeks ago
    series = daily_series(db, item.owner_id, item.id, SALES_TYPES, days=35)
    values = [v for _, v in fill_gaps(series, 35)]
    recent = sum(values[-7:]) / 7
    prior = sum(values[0:7]) / 7
    if prior > 0 and recent > prior * 2.5:
        return "Recent demand is much higher than 4 weeks ago; a seasonal shift may have left the purchasing plan behind."
    if prior > 0 and recent < prior * 0.4:
        return "Reported demand is much lower than 4 weeks ago; a seasonal drop may have left stock unsold."
    return None


def _forecast_error_flag(db: Session, item: InventoryItem) -> str | None:
    from models.waste_prediction import WastePrediction
    from services.forecasting import daily_series as ds

    preds = (
        db.query(WastePrediction)
        .filter(WastePrediction.owner_id == item.owner_id, WastePrediction.item_id == item.id)
        .all()
    )
    if not preds:
        return None
    # aggregate forecast vs actual waste over the last 30 days
    actual_waste = sum(daily_series(db, item.owner_id, item.id, WASTE_TYPES, days=30).values())
    predicted_total = sum(p.predicted_waste for p in preds)
    if predicted_total > 0 and actual_waste > 2 * predicted_total:
        return f"Forecast underestimated waste ({predicted_total:g} predicted vs {actual_waste:g} actual)."
    return None