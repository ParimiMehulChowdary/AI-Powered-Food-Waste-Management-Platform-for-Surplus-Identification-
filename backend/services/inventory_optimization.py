"""Inventory optimization / reorder recommendations.

Computes a recommended order quantity balancing forecast demand, safety stock,
lead time and the expiry constraint so that perishable items are never
over-stocked beyond what can be sold before expiry.
"""
from __future__ import annotations

from models.inventory_item import InventoryItem

DEFAULT_LEAD_TIME_DAYS = 2.0
SAFETY_STOCK_DAYS = 1.0


def optimize_item(item: InventoryItem, forecast: dict, category=None, lead_time_days: float = DEFAULT_LEAD_TIME_DAYS) -> dict:
    total_demand = forecast.get("total_demand", 0.0) or 0.0
    horizon = int(forecast.get("horizon_days", 7))
    days_left = forecast.get("days_to_expiry")
    stock = item.quantity or 0.0

    daily_demand = total_demand / horizon if horizon else 0.0
    safety_stock = daily_demand * SAFETY_STOCK_DAYS

    # how many days of sales we can plan for before expiry
    cover_days = horizon
    if days_left is not None and days_left > 0:
        cover_days = min(horizon, days_left)

    if cover_days <= 0:
        return _result(item, 0.0, daily_demand, stock, cover_days, "Item is near or past expiry; do not reorder.")

    demand_until_cover = daily_demand * cover_days
    target_stock = demand_until_cover + safety_stock
    recommended = max(target_stock - stock, 0.0)

    # capacity / safety cap: never recommend more than the demand that can clear before expiry
    cap = max(demand_until_cover - stock, 0.0)
    recommended = min(recommended, cap)

    reason = (
        f"Forecast demand is {total_demand:g} units over {horizon} day(s) "
        f"({daily_demand:g}/day) with {cover_days} day(s) of sales possible before expiry. "
        f"Safety stock added for {SAFETY_STOCK_DAYS:g} day(s)."
    )
    return _result(item, recommended, daily_demand, stock, cover_days, reason)


def _result(item, recommended, daily_demand, stock, cover_days, reason) -> dict:
    return {
        "item_id": item.id,
        "item_name": item.name,
        "current_quantity": round(stock, 2),
        "recommended_quantity": round(max(recommended, 0.0), 2),
        "daily_demand": round(daily_demand, 3),
        "cover_days": cover_days,
        "expected_stock_after_reorder": round(stock + max(recommended, 0.0), 2),
        "reason": reason,
        "unit": item.unit,
    }