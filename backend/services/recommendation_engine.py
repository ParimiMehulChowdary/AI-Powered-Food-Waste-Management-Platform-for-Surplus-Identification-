"""AI action recommendation engine.

Generates prioritized, quantified actions for products at waste risk. Every
recommendation carries a reason grounded in actual data, an expected benefit
($), a suggested quantity and a deadline.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from models.inventory_item import InventoryItem
from models.recommendation import Recommendation

REC_TYPES = {
    "discount",
    "promotion",
    "reduce_next_purchase",
    "stop_reorder",
    "transfer_stock",
    "donate_surplus",
    "prioritize_sale",
    "relocate_high_visibility",
    "adjust_storage",
    "process_before_expiry",
    "mark_for_disposal",
    "reorder",
}


def severity_rank(level: str) -> int:
    return {"critical": 1, "high": 2, "moderate": 3, "low": 4}.get(level, 4)


def generate_for_item(
    item: InventoryItem,
    assessment: dict,
    forecast: dict | None = None,
    category=None,
    reorder_suggestion: dict | None = None,
) -> list[dict]:
    """Produce recommendation dicts for a single item."""
    level = assessment.get("risk_level", "low")
    if level not in ("high", "critical"):
        return []

    stock = item.quantity or 0.0
    cost = item.cost_per_unit or 0.0
    days_left = assessment.get("days_to_expiry")
    rank = severity_rank(level)

    recs: list[dict] = []

    total_demand = forecast["total_demand"] if forecast else 0.0
    surplus = max(stock - total_demand, 0.0) if forecast else 0.0

    surplus_source = "forecast demand" if forecast else "current sales velocity"

    if surplus > 0 and days_left is not None and days_left > 0:
        # Donate the surplus portion that cannot be sold before expiry.
        deadline = item.expiry_date or (datetime.utcnow() + timedelta(days=1))
        reason = (
            f"{stock:g} units in stock but only {total_demand:g} units forecast to sell before expiry "
            f"({days_left} day(s) left). Redirect {surplus:g} units to donation."
        )
        recs.append(_rec("donate_surplus", surplus, rank, reason, surplus * cost * 0.7, deadline, level))

        reason2 = (
            f"Offer a time-limited discount on ~{min(surplus, total_demand):g} units to lift sales "
            f"and recover value before expiry."
        )
        recs.append(_rec("discount", min(surplus, max(total_demand, 1)), rank, reason2, surplus * cost * 0.4, deadline, level))

        reason3 = f"Prioritize selling {surplus:g} units at high-visibility positions before expiry."
        recs.append(_rec("prioritize_sale", surplus, rank + 1, reason3, surplus * cost * 0.8, deadline, level))
    elif level == "critical":
        # depleted shelf life with no clear sell-through plan
        recs.append(_rec("process_before_expiry", stock, rank, "Process or cook before expiry to extend useful shelf life.", stock * cost * 0.5, item.expiry_date or (datetime.utcnow() + timedelta(hours=24)), level))

    if surplus > 0 and days_left is not None and days_left >= 3:
        recs.append(_rec(
            "reduce_next_purchase",
            surplus,
            rank + 1,
            f"Surplus of {surplus:g} units is forecast (stock {stock:g} vs demand {total_demand:g}). Reduce the next purchase by this amount.",
            surplus * cost * 0.6,
            None,
            level,
        ))

    if reorder_suggestion and reorder_suggestion.get("recommended_quantity", 0) <= 0 and total_demand > 0:
        recs.append(_rec(
            "stop_reorder",
            0,
            rank + 1,
            "Stock already exceeds forecast demand; skip the next reorder to avoid overstocking.",
            surplus * cost * 0.5 if surplus else 0.0,
            None,
            level,
        ))

    if days_left is not None and days_left <= 0 and stock > 0:
        reason = f"{stock:g} units are past expiry ({abs(days_left)} days). Mark for disposal or donate only if still safe."
        recs.append(_rec("mark_for_disposal", stock, rank, reason, 0.0, datetime.utcnow(), level))

    return recs


def _rec(rec_type: str, quantity: float, priority: int, reason: str, benefit: float, deadline: datetime | None, level: str) -> dict:
    p = max(1, min(5, priority + severity_rank(level)))
    return {
        "recommendation_type": rec_type,
        "recommended_quantity": round(max(quantity, 0.0), 2),
        "priority": p,
        "reason": reason,
        "expected_benefit": round(max(benefit, 0.0), 2),
        "deadline": deadline,
    }


def regenerate_for_owner(db, owner_id: int) -> int:
    """Delete active pending recommendations so the latest run is authoritative."""
    removed = db.query(Recommendation).filter(
        Recommendation.owner_id == owner_id,
        Recommendation.status == "pending",
    ).delete()
    return removed or 0