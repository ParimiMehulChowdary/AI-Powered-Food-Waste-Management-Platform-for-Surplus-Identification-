"""Smart surplus allocation engine.

Predicts surplus quantity, estimates the remaining safe/useful period, and
suggests an allocation (donation / promotion / transfer) ranked by urgency.
Reuses existing donation history and the donation-partner registry — it never
invents NGO data.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models.inventory_item import InventoryItem
from models.transaction import Transaction
from models.donation_partner import DonationPartner


def _historical_donation_demand(db: Session, owner_id: int, item_id: int, category_id: int | None, days: int = 90):
    from services.forecasting import utc_now, timedelta as _td  # noqa: F401

    since = datetime.utcnow() - _td(days=days)
    item_qty = (
        db.query(Transaction)
        .filter(
            Transaction.owner_id == owner_id,
            Transaction.item_id == item_id,
            Transaction.transaction_type == "donation",
            Transaction.transaction_date >= since,
        )
        .count()
    )
    # category-level demand is approximated from donations of items in the same category
    cat_qty = 0
    if category_id:
        from models.inventory_item import InventoryItem as II
        ids = [i.id for i in db.query(II.id).filter(II.owner_id == owner_id, II.category_id == category_id).all()]
        if ids:
            cat_qty = (
                db.query(Transaction)
                .filter(
                    Transaction.owner_id == owner_id,
                    Transaction.transaction_type == "donation",
                    Transaction.item_id.in_(ids),
                    Transaction.transaction_date >= since,
                )
                .count()
            )
    return item_qty, cat_qty


def allocate_for_item(
    db: Session,
    item: InventoryItem,
    forecast: dict,
    assessment: dict,
    category=None,
) -> dict | None:
    """Return a surplus allocation suggestion for one item, or None."""
    surplus = forecast.get("total_surplus", 0.0)
    if surplus <= 0:
        return None

    stock = item.quantity or 0.0
    days_left = forecast.get("days_to_expiry")
    level = assessment.get("risk_level", "low")
    perishability = (category.perishability_risk if category else None) or "medium"

    safe_period = days_left if days_left is not None and days_left >= 0 else 0
    if safe_period <= 0:
        # still recommend disposal handling of expired items handled elsewhere
        return None

    # urgency: 1 (highest) to 5
    if safe_period <= 1:
        urgency = 1
    elif safe_period <= 3:
        urgency = 2
    elif safe_period <= 7:
        urgency = 3
    else:
        urgency = 4
    if perishability == "high":
        urgency = max(1, urgency - 1)

    # allocation type: prefer donation when partners or history exist
    partners = db.query(DonationPartner).filter(
        DonationPartner.owner_id == item.owner_id,
        DonationPartner.is_active == True,  # noqa: E712
    ).order_by(DonationPartner.capacity.desc()).all()

    item_hist, cat_hist = _historical_donation_demand(db, item.owner_id, item.id, item.category_id)
    has_history = (item_hist + cat_hist) > 0

    chosen = None
    allocation_type = "promotion"
    if partners or has_history:
        allocation_type = "donation"
        if partners:
            chosen = partners[0].name
            for p in partners:
                if p.capacity >= surplus:
                    chosen = p.name
                    break

    reason = (
        f"{surplus:g} units of '{item.name}' cannot clear forecast demand within {safe_period} day(s) "
        f"until expiry. "
    )
    if allocation_type == "donation":
        reason += "Match to donation."
        if chosen:
            reason += f" Suggested partner: {chosen}."
    elif allocation_type == "promotion":
        reason += "Offer at a discount or move to high-visibility location."

    return {
        "item_id": item.id,
        "item_name": item.name,
        "surplus_quantity": round(surplus, 2),
        "safe_period_days": safe_period,
        "urgency": urgency,
        "allocation_type": allocation_type,
        "suggested_partner": chosen,
        "reason": reason,
    }


def urgency_sort_key(allocation: dict) -> tuple:
    return (allocation["urgency"], -allocation["surplus_quantity"])